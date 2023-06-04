"""
A Backup Manager for automating Raspberry Pi SD card backups.

This class encapsulates the functionality for backing up an SD card on a 
Raspberry Pi device and compressing it using gzip. It also sends notifications 
to Telegram at various stages of the process.

Attributes
----------
backup_dest : str
    The location where the backup will be saved, the filename will be backup.img
config_file : str
    The path to the configuration file that contains the Telegram bot token and chat ID.
device_name : str
    The name of the device that is being backed up.
timeout : int
    The maximum time to wait for the backup and compression commands to complete before timing out.
block_size : int
    The block size in bytes for the dd command used to create the backup.

Methods
-------
_init_logger():
    Initializes the logger with handlers for console and file outputs.
load_telegram_config():
    Loads the Telegram bot token and chat ID from the configuration file.
send_notification(body: str):
    Sends a notification to a Telegram chat using the configured bot.
execute_command(command: str, message: str):
    Executes a given shell command and sends notifications at the start and end of the process.
execute_backup():
    Executes the backup command.
execute_gzip():
    Executes the compression command.
cleanup(backup_success: bool, compression_success: bool):
    Deletes the backup file if either the backup or compression failed.
run():
    Entry point for the backup and compression process. 
    It prevents multiple instances from running simultaneously by using a lock file.

Note
----
If the backup or compression process fails, a notification is sent to Telegram.
If the backup or compression process times out, a notification is sent to Telegram.
If an exception is raised during the process, a notification is sent to Telegram.

"""

import configparser
import argparse
import subprocess
import requests
import logging
import os
import fcntl
import datetime
import time

class BackupManager:
    def __init__(
            self,
            backup_dest: str,
            config_file: str,
            device_name: str,
            timeout: int,
            block_size: int) -> None:
        self.backup_dest: str = backup_dest
        self.config_file: str = config_file
        self.device_name: str = device_name
        self.timeout: int = timeout
        self.block_size: int = block_size
        self._init_logger()
        self.load_telegram_config()

    def _init_logger(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        log_path = os.path.join(
            os.path.dirname(
                os.path.abspath(__file__)),
            'backup_manager.log')
        file_handler = logging.FileHandler(log_path)
        console_handler = logging.StreamHandler()

        file_handler.setLevel(logging.DEBUG)
        console_handler.setLevel(logging.INFO)

        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')
        console_format = logging.Formatter(
            '%(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(file_format)
        console_handler.setFormatter(console_format)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)    
        
    def load_telegram_config(self):
        if not os.path.exists(self.config_file):
            raise ValueError(f"The config file does not exist `{self.config_file}`.")
    
        self.logger.info("Loading Telegram bot token and chat ID...")
        self._read_config()

        if self.bot_token is None or self.chat_id is None:
            self.logger.critical(
                "Telegram bot token or chat ID not found. Exiting...")
            raise ValueError("Telegram bot token or chat ID not found.")

        self.logger.info("Telegram bot token and chat ID loaded.")       
        
    def _read_config(self):
        config = configparser.ConfigParser()
        config.read(self.config_file)

        self.bot_token = config['Telegram']['bot_token'].strip('"')
        self.chat_id = config['Telegram']['chat_id'].strip('"')
        
    def send_notification(self, body: str) -> None:
        try:
            self.logger.info(f"Sending Notification to Telegram: '{body}'")
            tg_api_link = f"https://api.telegram.org/bot{self.bot_token}/sendMessage?chat_id={self.chat_id}&parse_mode=Markdown&text={body}"
            response = requests.get(tg_api_link)
            if response.status_code == 200:
                self.logger.info("Notification sent to Telegram.")
            else:
                self.logger.error(
                    f"Failed to send notification to Telegram, status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.logger.error(
                "Failed to send notification to Telegram",
                exc_info=True)
            
    def execute_command(self, command: str, message: str) -> bool:
        try:
            self.send_notification(f"*{message.capitalize()} process started.*")
            self.logger.info(f"Running command: '{command}'...")
            
            process = subprocess.Popen(
                command,
                shell=True,
                stderr=subprocess.PIPE)
            
            start_time = time.time()
            last_size = -1

            while True:
                if process.poll() is not None:  # If the process has finished
                    stdout, stderr = process.communicate()
                    break
                
                # Check if timeout exceeded
                if time.time() - start_time > self.timeout:
                    self.logger.error(f"{message.capitalize()} process timed out.")
                    self.send_notification(f"*ERROR*: {message.capitalize()} process timed out.")
                    process.terminate()
                    return False

                # Check if the file size has changed in the last 5 seconds
                time.sleep(5)  # adjust sleep duration as needed
                if os.path.exists(self.backup_file_dest):
                    current_size = os.path.getsize(self.backup_file_dest)
                    if current_size != last_size:
                        last_size = current_size
                    else:
                        self.logger.error(f"{message.capitalize()} process stalled.")
                        self.send_notification(f"*ERROR*: {message.capitalize()} process stalled.")
                        process.terminate()
                        return False
            
            self.logger.info(f"{message.capitalize()} process completed.")
            self.send_notification(f"*{message.capitalize()} process completed.*")
            return True

        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.send_notification(
                f"Backup failed due to an unexpected error: {e}")

        
            
    def execute_backup(self):
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        self.backup_file_dest = os.path.join(self.backup_dest, f"{date}_{self.device_name}-backup.img")
        backup_command: str = f"sudo dd if=/dev/mmcblk0 of={self.backup_file_dest} bs={self.block_size}"
        self.send_notification(
            f"Starting Backup for device: `{self.device_name}`...")    
        return self.execute_command(backup_command, "backup")

    def execute_gzip(self):
        gzip_command: str = f"gzip -k {self.backup_dest}"
        return self.execute_command(gzip_command, "compression")

    def cleanup(self, backup_success: bool, compression_success: bool) -> None:
        if not backup_success:
            backup_file = self.backup_file_dest
        elif not compression_success:
            backup_file = self.backup_file_dest + ".gz"
        else:
            return
        
        if os.path.exists(backup_file):    
            try:
                self.logger.info("Deleting incomplete backup file...")
                os.remove(backup_file)
                self.logger.info("Incomplete backup file deleted.")
            except Exception as e:
                self.logger.error(
                    f"Failed to delete incomplete backup file. Error: {e}",
                    exc_info=True)

        self.send_notification("*Cleaning Done.*")

    def run(self):
        lock_file: str = "/tmp/backup_manager.lock"
        # Check if another instance of this script is already running
        try:
            lock_file_descriptor = os.open(
                lock_file, os.O_CREAT | os.O_TRUNC | os.O_WRONLY)
        except OSError as e:
            self.logger.error(
                f"Could not open or create lock file: {e}. Exiting...")
            return

        # Try to acquire an exclusive lock on the lock file
        try:
            fcntl.lockf(lock_file_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as e:
            self.logger.error(
                f"An Instance of this script is already running: {e}. Exiting...")
            return
        
        # Check if the backup destination exists and is a directory
        if not (os.path.exists(self.backup_dest) and os.path.isdir(self.backup_dest)):
            raise ValueError(
                f"Backup destination '{self.backup_dest}' does not exist or is not a directory.")
                
        backup_success = False
        compression_success = False
        
        try:
            backup_success = self.execute_backup()
            if backup_success:
                compression_success = self.execute_gzip()
            
        except KeyboardInterrupt:
            self.logger.error("Backup process interrupted by keyboard.")
            self.send_notification(
                "Backup process interrupted by keyboard.")
        except Exception as e:
            # Catch any other exceptions that might have been missed.
            self.logger.error(f"Unexpected error: {e}")
            self.send_notification(
                f"Backup failed due to an unexpected error: {e}")
        finally:
            if backup_success and compression_success:
                self.logger.info(f"DONE - Backup for device `{self.device_name}` completed successfully.")
                self.send_notification(f"*DONE* - Backup for device `{self.device_name}` completed successfully.")
            else:
                # If backup or compression failed, delete the incomplete file(s).
                self.logger.info("FAIL - Backup was not completed successfully, rolling back changes...")
                self.send_notification("*FAIL* - Backup was not completed successfully, rolling back changes...")
                self.cleanup(backup_success, compression_success)
                
            self.logger.info("Removing lock file...")
            try:
                os.close(lock_file_descriptor)
                os.remove(lock_file)
                self.logger.info("Lock file removed.")
            except Exception as e:
                self.logger.error(
                    f"Failed to remove lock file: {e}",
                    exc_info=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup Manager for Raspberry Pi")
    parser.add_argument(
        "--backup_dest",
        type=str,
        help="Backup destination path",
        required=True)
    parser.add_argument(
        "--config_file",
        type=str,
        help="Config file path",
        required=True)
    parser.add_argument(
        "--device_name",
        type=str,
        default="device1",
        help="Device name")
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Timeout for backup and compression commands in seconds")
    parser.add_argument(
        "--block_size",
        type=int,
        default=4096,
        help="Block size for dd command in bytes")
    
    args = parser.parse_args()

    backup_manager = BackupManager(
        args.backup_dest,
        args.config_file,
        args.device_name,
        args.timeout,
        args.block_size)
    backup_manager.run()
