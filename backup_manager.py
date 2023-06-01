import configparser
import argparse
import subprocess
import requests
import logging
import os
import fcntl
import signal
import time

class BackupManager:
    def __init__(self, backup_file) -> None:
        if not os.path.isdir(os.path.dirname(backup_file)):
            raise ValueError("Invalid backup file path.")
        self.backup_file = backup_file
        self.backup_command = f"sudo dd if=/dev/mmcblk0 of={self.backup_file} bs=1M"
        self.lock_file = "/tmp/backup_manager.lock"
        self._init_logger()
        self.load_telegram_config()
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _init_logger(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backup_manager.log')
        file_handler = logging.FileHandler(log_path)
        console_handler = logging.StreamHandler()

        file_handler.setLevel(logging.DEBUG)
        console_handler.setLevel(logging.DEBUG)

        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        console_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(file_format)
        console_handler.setFormatter(console_format)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _signal_handler(self, signum, frame) -> None:
        self.logger.info("Received signal to stop backup process. Exiting...")
        self.send_notification("*Backup process stopped.*")
        self.cleanup(True)
        exit(0)


    def _read_config(self):
        config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")
        config.read(config_path)

        self.bot_token = config['Telegram']['bot_token'].strip('"')
        self.chat_id = config['Telegram']['chat_id'].strip('"')

        
        
    def load_telegram_config(self):
        self.logger.info("Loading Telegram bot token and chat ID...")
        self._read_config()
        
        if self.bot_token is None or self.chat_id is None:
            raise ValueError("Telegram bot token or chat ID not found.")
        self.logger.critical("Telegram bot token or chat ID not found. Exiting...")

        self.logger.info("Telegram bot token and chat ID loaded.")

    def send_notification(self, body: str) -> None:
        try:
            self.logger.info(f"Sending Notification to Telegram: '{body}'")
            tg_api_link = f"https://api.telegram.org/bot{self.bot_token}/sendMessage?chat_id={self.chat_id}&parse_mode=Markdown&text={body}"
            response = requests.get(tg_api_link)
            if response.status_code == 200:
                self.logger.info("Notification sent to Telegram.")
            else:
                self.logger.error(f"Failed to send notification to Telegram, status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to send notification to Telegram", exc_info=True)

    def execute_backup(self):
        """Executes the backup command with error handling."""
        try:
            self.logger.info("Running backup command...")
            self.send_notification("*Backup process started.*")
            
            start = time.time()
            subprocess.run(self.backup_command, shell=True, stderr=subprocess.STDOUT, timeout=3600)
            end = time.time()
            
            self.logger.info("Backup process completed. Time taken: %.2f minutes", end-start / 60)
            self.send_notification(f"*Backup process completed. Time taken: %.2f minutes*", end-start / 60)
            return True
        except subprocess.TimeoutExpired:
            self.logger.error("Backup process timed out.")
            self.send_notification("*ERROR*: Backup process timed out.") # add optional argument to determine severity of error. i.e. critical, warning, info etc.
            return False
        except Exception as e:
            self.handle_error(e)
            return False

    def execute_gzip(self):
        """Executes the gzip command with error handling."""
        gzip_command = f"gzip -c {self.backup_file}"
        try:
            self.logger.info("Running gzip command...")
            subprocess.run(gzip_command, shell=True, stderr=subprocess.STDOUT, timeout=3600)
            self.logger.info("Compression process completed.")
            self.send_notification("*Compression process completed.*")
            return True
        except subprocess.TimeoutExpired:
            self.logger.error("Compression process timed out.")
            self.send_notification("*Compression process timed out.*")
            return False
        except Exception as e:
            self.handle_error(e)
            return False

    def handle_error(self, e):
        if isinstance(e, subprocess.CalledProcessError):
            self.logger.error("Backup or compression process failed.")
            error_message = f"Backup or compression process failed with error: {e.output.decode()}"
            self.send_notification(error_message)
        else:
            self.logger.error(f"Unexpected error: {e}")
            self.send_notification(f"Backup failed due to an unexpected error: {e}")

    def cleanup(self, error_thrown: bool):
        if error_thrown:
            if os.path.exists(self.backup_file):
                try:
                    self.logger.info("Deleting incomplete backup file...")
                    os.remove(self.backup_file)
                    self.logger.info("Incomplete backup file deleted.")
                except Exception as e:
                    self.logger.error(f"Failed to delete incomplete backup file. Error: {e}", exc_info=True)
            
            self.send_notification("*Cleaning Done.*")



    def run(self, device_name: str = "device1"):       
        # Check if another instance of this script is already running
        try:
            lock_file_descriptor = os.open(self.lock_file, os.O_CREAT | os.O_TRUNC | os.O_WRONLY)
        except OSError as e:
            self.logger.error(f"Could not open or create lock file: {e}. Exiting...")
            exit(1)
        
        # Try to acquire an exclusive lock on the lock file
        try:
            fcntl.lockf(lock_file_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as e:
            self.logger.error(f"An Instance of this script is already running: {e}. Exiting...")
            exit(1)
        
        try:    
            self.send_notification(f"*Starting Backup for device: '{device_name}'...*")
            # Execute backup and compression commands sequentially.
            if not self.execute_backup():
                # If backup fails, delete the incomplete backup file and exit.
                self.cleanup(error_thrown=True)
                return
            
            if not self.execute_gzip():
                # If compression fails, delete the incomplete backup file and exit.
                self.cleanup(error_thrown=True)
                return

            # Backup and compression finished successfully.
            self.logger.info("Backup and compression finished successfully.")
            self.send_notification("*Backup and compression finished successfully.*")
        except KeyboardInterrupt:
            # Catch keyboard interrupt (Ctrl+C) and exit.
            self.logger.error("Backup process interrupted by keyboard.")
            self.cleanup(error_thrown=True)
        except Exception as e: 
            # Catch any other exceptions that might have been missed.
            self.handle_error(e)
            self.cleanup(error_thrown=True)
        finally:
            # Release the lock on the lock file and delete it.
            self.logger.info("Removing lock file...")
            os.close(lock_file_descriptor)
            os.remove(self.lock_file)
            self.logger.info("Lock file removed.")
            
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup Manager")
    parser.add_argument("backup_file", help="Backup image location")

    args = parser.parse_args()

    backup_manager = BackupManager(args.backup_file)
    backup_manager.run("PlexServer")