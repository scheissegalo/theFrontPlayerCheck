#!/usr/bin/python3
import time
import re
import requests
import xml.etree.ElementTree as ET
from steam.webapi import WebAPI
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get your steam API key from .env file
api_key = os.getenv('STEAM_API_KEY')
api = WebAPI(key=api_key)

# Get Discord webhook from .env file
webhook_url = os.getenv('DISCORD_WEBHOOK')

# Initialize a variable to keep track of the number of players online
players_online = 0

# Function to convert Steam ID to player name using Steam Community API
def get_player_name(steam_id):
#    print ("Fetch Steam Name")
    url = f'http://steamcommunity.com/profiles/{steam_id}/?xml=1'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            steam_id64 = root.findtext('steamID64')
            steam_name = root.findtext('steamID')
            return steam_id64, steam_name
    except requests.exceptions.RequestException as e:
        print(f"Error fetching player name: {e}")
    return None, None

# Func to send to discord
def send_to_discord(webhook_url, message):
    data = {"content": message}
    response = requests.post(webhook_url, json=data)
    if response.status_code != 204:
        print(f"Error sending message to Discord: \
              {response.status_code} - {response.text}")
# Log watcher def
def watch_log_file(log_file_path):
    # This part starts the log at EOF, so we don't get dupes
    with open(log_file_path, 'r') as file:
        file_position = file.seek(0, 2)

    while True:
        with open(log_file_path, 'r') as file:
            file.seek(file_position)
            lines = file.readlines()
            file_position = file.tell()

        for line in lines:
            process_line(line)

        time.sleep(5)

# This defines what to look for in log entries
def process_line(line):
    # Check for join requests
    if 'Join request:' in line:
        join_match = re.search(r'\?ppid=(\d+)\?hn=[^?]+\?Name=([^?]+)', line)
        if join_match:
            steam_id, player_name = join_match.groups()
            process_join(steam_id, player_name)

    # Check for player leaving
    elif 'LogPlayer: player leave game' in line:
        leave_match = re.search(r'account=STEAM:(\d+)', line)
        if leave_match:
            steam_id = leave_match.group(1)
            process_leave(steam_id)

# Function to check bans and send a message to another webhook if needed
def check_and_notify_bans(player_name, steam_id, player_info):
    if player_info['NumberOfVACBans'] > 0 or player_info['NumberOfGameBans'] > 0:
        another_webhook_url = os.getenv('ANOTHER_DISCORD_WEBHOOK')
        profile_url = f"https://steamcommunity.com/profiles/{steam_id}"
        bans_message = (
            f"❗❗❗**Warning Player with VAC Ban**❗❗❗\n"
            f"✅Player **{player_info['SteamId']} - {player_name}** {profile_url} connected\n"
            f"**Vac Banned:** {player_info['VACBanned']}\n"
            f"**Number Of VAC Bans:** {player_info['NumberOfVACBans']}\n"
            f"**Days Since Last Ban:** {player_info['DaysSinceLastBan']}\n"
            f"**Number Of Game Bans:** {player_info['NumberOfGameBans']}\n"
        )
        send_to_discord(another_webhook_url, bans_message)

# Tattle tail when they join
def process_join(steam_id, player_name):
    global players_online
    try:
        response = api.call('ISteamUser.GetPlayerBans', steamids=steam_id)
        if response and 'players' in response:
            players_online += 1
            player_info = response['players'][0]
            profile_url = f"https://steamcommunity.com/profiles/{steam_id}"
            if player_info['NumberOfVACBans'] > 0 or player_info['NumberOfGameBans'] > 0:
                log_message = (
                    f"❗❗❗**Warning Player with VAC Ban**❗❗❗\n"
                    f"✅Player **{player_info['SteamId']} - {player_name}** {profile_url} connected\n"
                    f"**Vac Banned:** {player_info['VACBanned']}\n"
                    f"**Number Of VAC Bans:** {player_info['NumberOfVACBans']}\n"
                    f"**Days Since Last Ban:** {player_info['DaysSinceLastBan']}\n"
                    f"**Number Of Game Bans:** {player_info['NumberOfGameBans']}\n"
                    f"**Players Online:** {players_online}\n"
                )
            else:
                log_message = (
                    f"✅Player **{player_info['SteamId']} - {player_name}** {profile_url} connected\n"
                    f"**VacBanned:** {player_info['VACBanned']}\n"
                    f"**Players Online:** {players_online}\n"
                )
            log_to_file(log_message)
            send_to_discord(webhook_url, log_message)

            # Check and notify about bans
            check_and_notify_bans(player_name, steam_id, player_info)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching player bans: {e}")

# Leave event isn't much because the log just gives us steam ID.
def process_leave(steam_id):
    global players_online
    #print ("Processing Leave")
    players_online -= 1
    steam_name = get_player_name(steam_id)
    leave_message = f"❌{steam_name} has left the server\n**Players Online:** {players_online}"
    #print (f"Leave Message: {leave_message}")
    log_to_file(leave_message)
    send_to_discord(webhook_url, leave_message)

# Func to log the information to a file
def log_to_file(message, log_file='player_log.txt'):
    with open(log_file, 'a', encoding='utf-8') as file:
        file.write(message + '\n')

# Replace this with your log file path
log_file_path = os.getenv('LOG_FILE_PATH')
