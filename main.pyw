## config imports 
import pathlib
import json

## light imports
from flux_led import WifiLedBulb

## web imports
import webbrowser
import requests
import urllib.parse
import http.server
import socketserver

## image imports
import PIL.Image
import colorthief

## misc imports
from datetime import datetime

## tkinter imports
from tkinter import *
from tkinter import ttk

class Window():
    def __init__(self, master, config, api):
        ## window setup
        self.master = master
        self.master.title("Spotify Light Sync")
        self.master.geometry("500x500")
        self.master.resizable(False, False)
        self.master.after(1, self.update)
        self.colors = {"background": "grey50", "foreground": "grey40", "label": "grey60"}
        self.master.configure(bg=self.colors['background'])

        ## sets the config and api objects, and passes self to them
        self.config = config
        self.api = api
        self.config.window = self
        self.api.window = self

        ## sets the initial values of the variables
        self.bulbConnected = False
        ## checks if the config has been edited from the default values
        if self.config.getValue(keys=('Config_Constants','BULB_IP')) == "xxx.xxx.xxx.xxx" or self.config.getValue(keys=('Config_Constants','CLIENT_ID')) == "None" or self.config.getValue(keys=('Config_Constants','CLIENT_SECRET')) == "None":           
            self.validConfig = False
        else:
            self.validConfig = True
        ## current modes of color detection
        self.modes = ['Most Prominent', 'Average', 'Most Prominent Contrast', 'Average Contrast', 'Most Prominent Inverted', 'average inverted']
        self.mode = self.config.getValue(keys=('Session','mode'))

        ## creates the home screen 
        self.home()
        
        ## starts the main loop
        self.loopCount = 0
        self.master.mainloop()
        
    ## attempts to connect to the bulb, if successful, returns True, if not, returns False
    def ConnectToBulb(self):
        try:
            self.lights = lightsUpdater(self.config)
            self.lights.window = self
            self.bulbConnected = True
            self.writeToLog("Connected to bulb\n----------------------------------------------------------")
            return True
        except:
            self.bulbConnected = False
            return False
    
    def home(self):
        ## creates the screen, fills it with the elements and sets the colors
        Label(self.master, text="Spotify Light Sync", font=("Arial", 24), bg=self.colors['foreground']).place(relx = 0.5, 
                   rely = 0,
                   anchor = 'n')
        b = Button(self.master, text="Sign in", command=self.api.Get_OauthToken, bg=self.colors['foreground']).place(relx = 0.5, 
                   rely = 0.4,
                   anchor = 'center')
        
        Label(self.master, text="Mode", bg=self.colors['label']).place(relx = 0.5, 
                   rely = 0.3,
                   anchor = S)
        
        self.modeList = ttk.Combobox(self.master, values=self.modes, state='readonly')
        self.modeList.place(relx = 0.5, 
                   rely = 0.3,
                   anchor = N)
        self.modeList.current(self.mode)
        self.modeList.bind("<<ComboboxSelected>>", lambda event: self.__updateMode(self.modeList.get()))
        
        
        self.textlog = Text(self.master, height=16, width=58, bg=self.colors['foreground'])
        self.textlog.insert(END, "Welcome to Spotify Light Sync\n----------------------------------------------------------")
        self.textlog.config(state=DISABLED)
        self.textlog.place(relx = 0.5, 
                   rely = 0.7,
                   anchor = 'center')
        

    ## updates the window, checks if the config is valid, if the bulb is connected, and if the user is signed in, if so gets the current song and updates the lights
    def update(self):
        if not self.validConfig:
            self.writeToLog("Please fill in the configuration file\n----------------------------------------------------------")
            return
        elif not self.bulbConnected:
            if self.loopCount == 0:
                self.writeToLog("Attempting to connect to bulb, the application \nmay freeze for a moment.\n----------------------------------------------------------")
            elif self.loopCount == 1:
                if self.ConnectToBulb():
                    self.api.SignInLogic()
            elif self.loopCount == 2:
                self.writeToLog("Failed to connect to bulb, Please check the IP in The settings and restart the program\n----------------------------------------------------------")
                return
            self.loopCount += 1
            self.master.after(200, self.update)
              
        else:

            if self.api.Get_CurrentSong():
                color, brightness = self.api.get_average_color_brightness(self.mode)
                self.lights.setColor(color, brightness)
            self.master.after(2000, self.update)

    ## writes text to the log
    def writeToLog(self, text):
        self.textlog.config(state=NORMAL)
        self.textlog.insert(END, text + "\n")
        self.textlog.see(END)
        self.textlog.config(state=DISABLED)

    ## updates the mode in the config file and logs the change
    def __updateMode(self, mode):
        for i in range(len(self.modes)):
            if self.modes[i] == mode:
                self.mode = i   
                self.config.updateValue(('Session','mode'), self.mode)
                self.writeToLog(f"Mode set to {self.modes[i]}\n----------------------------------------------------------")
                color, brightness = self.api.get_average_color_brightness(self.mode)
                self.lights.setColor(color, brightness)

class ApiInterface():
    def __init__(self, config):
        self.config = config
        ## Spotify API Constants
        self.client_id = self.config.getValue(keys=('Config_Constants','CLIENT_ID'))
        self.client_secret = self.config.getValue(keys=('Config_Constants','CLIENT_SECRET'))
        
        self.redirect_uri = self.config.getValue(keys=('Constants','REDIRECT_URI'))
        self.auth_url = self.config.getValue(keys=('Constants','AUTH_URL'))
        self.token_url = self.config.getValue(keys=('Constants','TOKEN_URL'))
        self.api_base_url = self.config.getValue(keys=('Constants','API_BASE_URL'))

        ## Spotify API Variables
        self.access_token = self.config.getValue(keys=('Session','access_token'))
        self.refresh_token = self.config.getValue(keys=('Session','refresh_token'))
        self.expires_at = self.config.getValue(keys=('Session','expires_at'))

        self.prev_song = None
        self.image_url = None
        self.window = None

        self.isauthenticated = False

    ## returns True if signed in, False if not signed in, also attempts to use the refresh token if the access token is expired
    def SignInLogic(self): 
        ## Checks if the token hasnt been set yet
        if self.access_token == "None" or self.refresh_token == "None" or self.expires_at == "None":
            self.window.writeToLog("No access token found, please sign in\n----------------------------------------------------------")
            self.isauthenticated = False
            return False
        else:
            ## checks if the token is still valid
            if datetime.now().timestamp() < self.expires_at:
                self.window.writeToLog("Token still valid, you are signed in.\n----------------------------------------------------------")
                self.isauthenticated = True
                return True
            ## if the token is expired, it attempts to refresh the token
            elif self.Refresh_OauthToken():
                self.window.writeToLog("Token refreshed, you are signed in.\n----------------------------------------------------------")
                self.isauthenticated = True
                return True
            ## if the token cannot be refreshed, it prompts the user to sign in again
            else:
                self.window.writeToLog("Token expired, please sign in.\n----------------------------------------------------------")
                self.isauthenticated = False
                return False

    ## returns True if successful, False if unsuccessful
    def Get_OauthToken(self): 
        ## checks if the configuration file is valid or if the user is already signed in
        if self.window.validConfig == False:
            return False
        if self.isauthenticated:
            self.window.writeToLog("You are already signed in.\n----------------------------------------------------------")
            return True

        ## permission scopes and parameters for the authorization url
        scope = 'user-read-currently-playing user-read-email'
        params = {
                'client_id': self.client_id,
                'response_type': 'code',
                'scope': scope,
                'redirect_uri': self.redirect_uri, 
        }
        auth_url = f"{self.auth_url}?{urllib.parse.urlencode(params)}"

        ## opens the authorization url in the default browser
        webbrowser.open(auth_url)

        ## creates a local server to handle the authorization code
        class MyHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)
                code = params.get('code')
                if code:
                    self.server.auth_code = code[0]
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'Authorization successful. You can close this window.')
                else:
                    self.send_response(400)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'Authorization failed. please close this window and try again.')
        
        ## starts the server
        with socketserver.TCPServer(("localhost", 5000), MyHandler) as httpd:
            httpd.handle_request()
            if not hasattr(httpd, 'auth_code'):
                self.window.writeToLog("Authorization failed. Please try again.\n----------------------------------------------------------")
                self.isauthenticated = False
                return False

            auth_code = httpd.auth_code
        ## Exchange the authorization code for an access token
        token_data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }

        ## requests the access token and saves the response
        response = requests.post(self.token_url, data=token_data)
        token_info = response.json()
        ## checks if the response contains an error, if it does, it prompts the user to sign in again
        if 'error' in token_info:
            self.window.writeToLog("Authorization failed, Please try again.\n----------------------------------------------------------")
            self.isauthenticated = False
            return False

        ## saves the access token, refresh token and expiration time
        self.access_token = token_info['access_token']
        self.refresh_token = token_info['refresh_token']
        self.expires_at = datetime.now().timestamp() + token_info['expires_in']

        self.config.updateValue(('Session','access_token'), self.access_token)
        self.config.updateValue(('Session','refresh_token'), self.refresh_token)
        self.config.updateValue(('Session','expires_at'), self.expires_at)

        self.window.writeToLog("Authorization successful, You are now signed in.\n----------------------------------------------------------")
        self.isauthenticated = True
        return True
            
    ## returns True if successful, False if unsuccessful
    def Refresh_OauthToken(self):
        ## checks if the token is expired
        if datetime.now().timestamp() > self.expires_at:
            ## requests a new access token using the refresh token
            req_body = {
                    'grant_type': 'refresh_token',
                    'refresh_token': self.refresh_token,
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
            }
            ## saves the response, if the response contains an error, it returns False
            response = requests.post(self.token_url, data=req_body)
            token_info = response.json()
            if 'error' in token_info:
                return False
            
            ## saves the new access token and expiration time
            self.access_token = token_info['access_token']
            self.expires_at = datetime.now().timestamp() + token_info['expires_in']

            self.config.updateValue(('Session','access_token'), self.access_token)
            self.config.updateValue(('Session','expires_at'), self.expires_at)
            return True
    
    ## returns False if no song is playing, True if song is playing
    def Get_CurrentSong(self): 
        playing = False
        ## checks if the token is expired or if the user is signed in
        if datetime.now().timestamp() > self.expires_at:
            return False
        if not self.isauthenticated:
            return False
        
        ## requests the currently playing song
        headers = {
                'Authorization': f"Bearer {self.access_token}"
        }
        response = requests.get(self.api_base_url + "me/player/currently-playing", headers=headers)
        ## checks the response, if the response is 200, it checks if the song is different from the previous song
        if str(response) == "<Response [200]>":
            json_response = response.json()
            if json_response == None:
                return False
            elif self.prev_song != json_response['item']['name']:
                self.prev_song = json_response['item']['name']
                playing = True
                ## get image of the song
                self.image_url = json_response['item']['album']['images'][-1]['url']


        ## if the response is 401, it attempts to refresh the token and try again
        elif str(response) == "<Response [401]>":
            self.isauthenticated = False
            self.access_token = "None"
            if self.Refresh_OauthToken():
                return self.Get_CurrentSong()
            else:
                self.window.writeToLog("Error: \nFailed to refresh token, please sign in again.\n----------------------------------------------------------")

        ## if the response is 204, it means no song is playing and resets the previous song and image
        elif str(response) == "<Response [204]>":
            self.prev_song = None
            self.image_url = None
        ## if the response is anything else, it logs the response
        else:
            api.writeToLog(f"Error: {response}\n----------------------------------------------------------")
        return playing

    ## returns the average color and brightness of the image based on the mode
    def get_average_color_brightness(self, mode):
        
        ## downloads the image and converts it to RGB
        img = PIL.Image.open(requests.get(self.image_url, stream=True).raw)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        ## saves the image to a file, and gets the width and height
        width, height = img.size
        imagePath = f'{self.config.path}/image.jpg'
        img.save(imagePath)


        ## Most Prominent
        if mode == 0:
            colorthief_instance = colorthief.ColorThief(imagePath)
            color = colorthief_instance.get_color(quality=1)
            brightness = max(color[0], color[1], color[2])
            r = color[0]
            g = color[1]
            b = color[2]

            brightness = round(brightness)


        ## Average
        elif mode == 1: 
            img = img.resize((1, 1))
            r, g, b = img.getpixel((0, 0))
            brightness = max(r, g, b)
            brightness = round(brightness)

        ## Most Prominent With increased Contrast
        elif mode == 2:
            colorthief_instance = colorthief.ColorThief(imagePath)


            color = colorthief_instance.get_color(quality=1)
            brightness = ((color[0] + color[1] + color[2]) /3 )
            r = color[0]
            g = color[1]
            b = color[2]

            brightness = round(brightness)

        ## Average with increased Contrast
        elif mode == 3:
            img = img.resize((1, 1))
            r, g, b = img.getpixel((0, 0))
            brightness = (r + g + b) /3 
            brightness = round(brightness)

        ## Most Prominent Inverted
        elif mode == 4:
            colorthief_instance = colorthief.ColorThief(imagePath)
            color = colorthief_instance.get_color(quality=1)
            brightness = max(color[0], color[1], color[2])

            r = 255 - color[0]
            g = 255 - color[1]
            b = 255 - color[2]
            brightness = round(brightness)

        ## average inverted
        elif mode == 5:
            img = img.resize((1, 1))
            r, g, b = img.getpixel((0, 0))
            brightness = max(r, g, b)
            brightness = round(brightness)

            r = 255 - r
            g = 255 - g
            b = 255 - b

        ## returns the color and brightness
        return (r, g, b), brightness

class configManager():
    def __init__(self):
        ## Default Config
        defaultConfig = {'Constants': {'REDIRECT_URI': 'http://localhost:5000/callback', 'AUTH_URL': 'https://accounts.spotify.com/authorize', 'TOKEN_URL': 'https://accounts.spotify.com/api/token', 'API_BASE_URL': 'https://api.spotify.com/v1/'}, 
                              'Config_Constants': {'CLIENT_ID': 'None', 'CLIENT_SECRET': 'None', 'BULB_IP': 'xxx.xxx.xxx.xxx'}, 
                              'Session': {'access_token': 'None', 'refresh_token': 'None', 'expires_at': 0 , "mode": 0}}
        ## sets the path to the directory of the script, and the path to the config file
        self.path = pathlib.Path(__file__).parent.resolve()
        self.configpath = f'{self.path}/config.json'.replace("\"", "/")
        ## checks if the config file exists, if it doesnt, it creates it
        if not pathlib.Path(self.configpath).exists():
            with open(self.configpath, 'w') as f:
                json.dump(defaultConfig, f, indent=4)

        ## loads the config file
        with open(self.configpath) as f:
            self.config = json.load(f)

        self.window = None
    
    ## updates the value of a key in the config file, 
    def updateValue(self, keys, value): ## ONLY SUPPORTS 2 LEVELS OF NESTING 
        self.config[keys[0]][keys[1]] = value
        with open(self.configpath, 'w') as f:
            json.dump(self.config, f, indent=4)

    ## returns the value of a key in the config file
    def getValue(self, keys): ## ONLY SUPPORTS 2 LEVELS OF NESTING 
        returnvalue = self.config[keys[0]][keys[1]]
        return returnvalue


class lightsUpdater():
    def __init__(self, config):
        ## sets the config and connects to the lights
        self.config = config
        self.bulb = WifiLedBulb(config.getValue(keys=('Config_Constants','BULB_IP')))

        ## gets the current color and brightness of the light
        self.color = self.bulb.getRgb()
        self.brightness = self.bulb.brightness
        self.window = None
        self.minBrightness = 0

    ## sets the color and brightness of light variables
    def setColor(self, color, brightness, log=True):
        self.color = color
        self.brightness = brightness
        if self.brightness < self.minBrightness:
            self.brightness = self.minBrightness
        self.__updateLights(log)
    
    ## updates the lights with the current color and brightness
    def __updateLights(self, log=True):
        self.bulb.refreshState()
        if self.bulb.isOn():
            r = self.color[0]
            g = self.color[1]
            b = self.color[2]
            self.bulb.setRgb(r,g,b, brightness= self.brightness)
            if log:
                self.window.writeToLog(f"Song: {api.prev_song} \nColor: {r}, {g}, {b} Brightness: {self.brightness} \nMode: {self.window.modes[self.window.mode]}\n----------------------------------------------------------")


## declairs the objects
config = configManager()
api = ApiInterface(config)
window = Window(Tk(), config, api)