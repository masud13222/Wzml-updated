#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command, create
from os import path as ospath, getcwd
from aiofiles.os import path as aiopath, mkdir
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from bot import bot, user_data, DATABASE_URL
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.db_handler import DbManger
import logging

LOGGER = logging.getLogger(__name__)

# Default client configuration
DEFAULT_CLIENT_CONFIG = {
    "installed": {
        "client_id": "202264815644.apps.googleusercontent.com",
        "client_secret": "X4Z3ca8xfWDb1Voo-F9a7",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"]
    }
}

class RcloneManager:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        self._flow_dict = {}
        
    async def get_auth_url(self, user_id: int):
        flow = InstalledAppFlow.from_client_config(
            DEFAULT_CLIENT_CONFIG,
            self.SCOPES
        )
        flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            prompt='consent'
        )
        
        self._flow_dict[user_id] = flow
        
        user_dict = user_data.get(user_id, {})
        user_dict['oauth_config'] = {
            "created_at": str(datetime.utcnow())
        }
        user_data[user_id] = user_dict
        if DATABASE_URL:
            await DbManger().update_user_data(user_id)
            
        return auth_url
        
    async def save_token(self, user_id: int, code: str):
        if user_id not in self._flow_dict:
            raise Exception("No pending authorization found")
            
        flow = self._flow_dict[user_id]
        try:
            flow.fetch_token(code=code)
            creds = flow.credentials
            
            token_data = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes,
                "expiry": creds.expiry.isoformat()
            }
            
            rclone_config = f"""[cine]
type = drive
client_id = {creds.client_id}
client_secret = {creds.client_secret}
token = {{"access_token":"{creds.token}","token_type":"Bearer","refresh_token":"{creds.refresh_token}","expiry":"{creds.expiry.isoformat()}"}}
team_drive = 
root_folder_id ="""

            path = f'{getcwd()}/wcl/'
            if not await aiopath.isdir(path):
                await mkdir(path)
            
            async with open(f"{path}{user_id}_cine.conf", 'w') as f:
                await f.write(rclone_config)
                
            user_dict = user_data.get(user_id, {})
            user_dict['cine'] = f'wcl/{user_id}_cine.conf'
            user_dict['token'] = token_data
            del user_dict['oauth_config']
            user_data[user_id] = user_dict
            
            if DATABASE_URL:
                await DbManger().update_user_data(user_id)
            
            del self._flow_dict[user_id]
            return True
            
        except Exception as e:
            if user_id in self._flow_dict:
                del self._flow_dict[user_id]
            user_dict = user_data.get(user_id, {})
            if 'oauth_config' in user_dict:
                del user_dict['oauth_config']
            if DATABASE_URL:
                await DbManger().update_user_data(user_id)
            raise Exception(f"Failed to save token: {str(e)}")

rclone_manager = RcloneManager()

async def rclone_command(client, message):
    user_id = message.from_user.id
    LOGGER.info(f"Rclone command from user {user_id}")
    try:
        auth_url = await rclone_manager.get_auth_url(user_id)
        buttons = ButtonMaker()
        buttons.ubutton("Authorize", auth_url)
        buttons.ibutton("Close", f"userset {user_id} close")
        button = buttons.build_menu(2)
        msg = """<b>Rclone Setup</b>
        
1. Click Authorize button
2. Allow permissions in browser
3. Copy the authorization code
4. Send the code here"""
        LOGGER.info(f"Sending auth URL to user {user_id}")
        await sendMessage(message, msg, button)
    except Exception as e:
        LOGGER.error(f"Error in rclone command: {str(e)}")
        await sendMessage(message, f"Error: {str(e)}")

async def is_auth_code(_, __, message):
    user_id = message.from_user.id
    user_dict = user_data.get(user_id, {})
    return 'oauth_config' in user_dict

async def rclone_auth(client, message):
    user_id = message.from_user.id
    try:
        code = message.text
        await rclone_manager.save_token(user_id, code)
        await sendMessage(message, "Rclone setup completed successfully!\nNow you can use -cine flag with mirror commands to upload to your drive.")
    except Exception as e:
        await sendMessage(message, f"Error: {str(e)}")

bot.add_handler(MessageHandler(rclone_command, filters=command(BotCommands.RcloneCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(rclone_auth, filters=create(is_auth_code) & CustomFilters.authorized))