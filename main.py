import base64
import threading
import time
import tkinter as tk
from datetime import datetime, timedelta
from dateutil.parser import parse
import webbrowser
import requests
import vlc
import sys
from dotenv import load_dotenv
from loguru import logger
import os
from pystray import MenuItem as item
import pystray
from PIL import Image, ImageDraw


# Setup Tray Icon
def create_image(width, height, color1, color2):
    # Generate an image and draw a pattern
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle([width // 2, 0, width, height // 2], fill=color2)
    dc.rectangle([0, height // 2, width // 2, height], fill=color2)
    return image

def on_clicked(icon, item):
    icon.stop()
    os._exit(0)

def setup_tray_icon():
    menu = (item('Exit', on_clicked),)
    icon = pystray.Icon("Jira Notify", Image.open("./assets/icon.png"), "Jira Notify", menu)
    icon.run()

# Run the tray icon in a separate thread
tray_thread = threading.Thread(target=setup_tray_icon)
tray_thread.start()

# Setup Environment
load_dotenv(override=True)
logger.add("jiraNotify.log", format="{time} {level} {message}", level="INFO", rotation="1 week", compression="zip")
_isWindows = sys.platform.startswith('win')
_isLinux = sys.platform.startswith('linux')

def load_env_variables():
    email = os.getenv("JIRA_EMAIL")
    if not email or email == "":
        raise Exception("Email not found. Please set JIRA_EMAIL in your environment variables.")
    jira_api_token = os.getenv("JIRA_API_TOKEN")
    if not jira_api_token or jira_api_token == "":
        raise Exception("JIRA API token not found. Please set JIRA_API_TOKEN in your environment variables.")
    tempo_api_token = os.getenv("TEMPO_API_TOKEN")
    if not tempo_api_token or tempo_api_token == "":
        raise Exception("TEMPO token not found. Please set TEMPO_API_TOKEN in your environment variables.")
    media_file_path = os.getenv("MEDIA_FILE_PATH")
    if not media_file_path or media_file_path == "":
        raise Exception("MEDIA_FILE_PATH not found. Please set MEDIA_FILE_PATH in your environment variables.")
    return email, jira_api_token, tempo_api_token, media_file_path

def fetch_current_user_account_id(email, api_token):
    """Fetch the current user's accountId using the Jira Cloud REST API with Basic Authentication."""
    credentials = f"{email}:{api_token}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Accept": "application/json"
    }
    response = requests.get("https://keepgenius.atlassian.net/rest/api/3/myself", headers=headers)
    if response.status_code == 200:
        return response.json()['accountId']
    else:
        raise Exception(f"Failed to fetch user details: {response.status_code}, Reason: {response.text}")

def is_user_booked_on_workday(email, jira_api_token, tempo_api_token, check_date):
    try:
        user_id = fetch_current_user_account_id(email, jira_api_token)
        logger.info(f"User ID: {user_id}")
    except Exception as e:
        return False, str(e)
    
    url = "https://api.tempo.io/core/3/worklogs"
    
    if not isinstance(check_date, datetime):
        check_date = parse(check_date)
    
    check_date_str = check_date.strftime('%Y-%m-%d')
    
    if check_date.weekday() > 4:  # 0: Monday, 6: Sunday
        return True, "Selected day is not a workday."
    
    headers = {"Authorization": f"Bearer {tempo_api_token}"}
    params = {
        "from": check_date_str,
        "to": check_date_str,
        "worker": user_id
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        worklogs = response.json()
        if worklogs['metadata']['count'] > 0:
            return True, "User has booked hours on this workday."
        else:
            return False, "No hours booked on this workday."
    else:
        return False, f"API Error: {response.status_code}"


class JiraNotify:
    def __init__(self):
        logger.info("JiraNotify started")
        self.root = tk.Tk()
        self.video_path = os.getenv("MEDIA_FILE_PATH")
        self.hours_booked = False
        self.configure_window()
        self.create_widgets()
        self.setup_vlc(self.video_path)
        self.playlist.play()
        self.root.mainloop()


    def configure_window(self):
        logger.info("JiraNotify window configured")
        self.root.configure(bg='black')
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.title("JiraNotify")
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = 640
        window_height = 500
        x_coordinate = (screen_width / 2) - (window_width / 2)
        y_coordinate = (screen_height / 2) - (window_height / 2)
        self.root.geometry(f"{window_width}x{window_height}+{int(x_coordinate)}+{int(y_coordinate)}")
        header = tk.Label(self.root, text="JiraNotify", bg="red", fg="white", font=("Arial", 24))
        header.pack()

    def create_widgets(self):
        logger.info("JiraNotify widgets created")
        self.reminder_text_area = tk.Text(self.root, height=4, width=50, bg="black", fg="white", border=0, highlightthickness=0, relief='ridge')
        self.reminder_text_area.insert(tk.END, "Hallo Kollege.. du hast heute noch keine Stunden gebucht..\n\nBitte bedenke die mögliche Reaktion von Florian!")
        self.reminder_text_area.config(state=tk.DISABLED, font=("Arial", 16))
        self.reminder_text_area.pack()
        self.video_frame = tk.Frame(self.root)
        self.canvas = tk.Canvas(self.video_frame, bg="black", border=0, highlightthickness=0, relief='ridge')
        self.canvas.pack(fill=tk.BOTH, expand=1)
        self.video_frame.pack(fill=tk.BOTH, expand=1)
        self.link_button = tk.Button(self.root, text="Visit Website and Close", command=self.open_website_and_close)
        self.link_button.pack()

    def setup_vlc(self, video):
        logger.info("VLC setup done")
        args = []
        if _isLinux:
            args.append('--no-xlib')
        self.Instance = vlc.Instance(args)
        self.player = self.Instance.media_player_new()
        self.playlist = self.Instance.media_list_player_new()
        self.playlist.set_media_player(self.player)
        self.media_list = self.Instance.media_list_new([self.Instance.media_new(video)])
        self.playlist.set_media_list(self.media_list)
        if _isWindows:
            self.player.set_hwnd(self.canvas.winfo_id())
        elif _isLinux:
            self.player.set_xwindow(self.canvas.winfo_id())

    def play_video(self):
        self.openPopup()
        logger.info("Video played")

    def open_website_and_close(self):
        logger.info("Website opened and window closed")
        webbrowser.open('https://keepgenius.atlassian.net/plugins/servlet/ac/io.tempo.jira/tempo-app#!/my-work/week?type=TIME')
        if self.playlist.is_playing():
            self.playlist.stop()
        self.root.destroy()

if __name__ == "__main__":
    lastDayBooked = None
    email, jira_api_token, tempo_api_token, media_path = load_env_variables()

    while True:        
        if lastDayBooked != datetime.today().day:
            booked, message = is_user_booked_on_workday(email=email, jira_api_token=jira_api_token, tempo_api_token=tempo_api_token, check_date=datetime.today())
            logger.info(f"Booked: {booked}, Message: {message}")
            if not booked:
                JiraNotify()
                time.sleep(300)
            else:
                lastDayBooked = datetime.today().day
