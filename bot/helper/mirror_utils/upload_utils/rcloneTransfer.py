#!/usr/bin/env python3
from asyncio import create_subprocess_shell, subprocess
from os import path as ospath
from re import findall as re_findall
from bot import LOGGER, user_data
from bot.helper.ext_utils.bot_utils import cmd_exec
from json import loads
from aiofiles.os import path as aiopath
from time import time


class RcloneTransferHelper:
    def __init__(self, listener=None, name=None, path=None):
        self.__listener = listener
        self.name = name
        self.__path = path
        self.__start_time = time()
        self.__processed_bytes = 0
        self.is_cancelled = False
        self.__is_errored = False
        self.__status = None
        self.__transferred_size = '0 B'
        self.__percentage = '0%'
        self.__speed = '0 B/s'
        self.__eta = '-'
        self.__user_id = self.__listener.message.from_user.id
        self.__total_files = 0
        self.__transferred_files = 0
        self.__total_folders = 0
        self.__transferred_folders = 0
        self.__total_size = 0
        self.__engine = 'Rclone v2'

    async def __user_settings(self):
        user_dict = user_data.get(self.__user_id, {})
        return user_dict.get('cine', '')

    async def upload(self, file_path):
        rclone_conf = await self.__user_settings()
        if not rclone_conf:
            raise Exception('Rclone configuration not found! Configure it using /rclone command')

        rclone_path = f"{ospath.dirname(ospath.dirname(ospath.dirname(ospath.dirname(__file__))))}/{rclone_conf}"
        if not await aiopath.exists(rclone_path):
            raise Exception('Rclone configuration file not found!')

        cmd = ['rclone', 'copy', '--config', rclone_path, str(file_path), 'cine:', '-P']
        LOGGER.info(f"Upload Command: {cmd}")

        self.__status = await create_subprocess_shell(" ".join(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        while True:
            try:
                if self.is_cancelled:
                    self.__status.kill()
                    raise Exception('Upload cancelled!')
                    
                output = (await self.__status.stdout.readline()).decode().strip()
                if not output:
                    break

                if "Transferred:" in output:
                    info = output.split(',')
                    self.__transferred_size = info[0].replace("Transferred:", "").strip()
                    self.__percentage = info[1].strip()
                    self.__speed = info[2].strip()
                    self.__eta = info[3].replace("ETA", "").strip()
                    
                elif "Checks:" in output:
                    info = re_findall(r'Checks:\s+([\d.]+)', output)
                    if info:
                        self.__total_files = int(info[0])
                        
                elif "Transferred:" in output and "%" not in output:
                    info = re_findall(r'Transferred:\s+(\d+) / (\d+), (\d+)', output) 
                    if info:
                        self.__transferred_files, self.__total_files, self.__transferred_folders = map(int, info[0])
                        
                elif "Errors:" in output:
                    info = re_findall(r'Errors:\s+(\d+)', output)
                    if info and int(info[0]) > 0:
                        raise Exception(f"Got {info[0]} errors during upload!")

            except Exception as e:
                if not str(e) == 'Upload cancelled!':
                    LOGGER.error(f"Error in rclone upload: {str(e)}")
                self.__is_errored = True
                break

        stdout, stderr = await self.__status.communicate()
        
        if self.__status.returncode != 0:
            err_message = stderr.decode().strip()
            LOGGER.error(f"Rclone upload error: {err_message}")
            raise Exception(err_message)

        result = await cmd_exec(['rclone', 'link', '--config', rclone_path, 'cine:'+ospath.basename(file_path)])
        if result[2] != 0:
            LOGGER.error(f"Error getting link: {result[1]}")
            raise Exception(result[1])
            
        return result[0]

    @property
    def speed(self):
        try:
            return float(self.__speed.split()[0]) * 1024**(['B/s', 'KiB/s', 'MiB/s', 'GiB/s', 'TiB/s'].index(self.__speed.split()[1]))
        except:
            return 0

    @property
    def processed_bytes(self):
        try:
            return float(self.__transferred_size.split()[0]) * 1024**(['B', 'KiB', 'MiB', 'GiB', 'TiB'].index(self.__transferred_size.split()[1]))
        except:
            return 0

    async def cancel_download(self):
        self.is_cancelled = True
        if self.__status is not None:
            self.__status.kill()
            await self.__status.wait()
        LOGGER.info(f"Cancelling Upload: {self.name}")
        await self.__listener.onUploadError('Upload cancelled by user!') 