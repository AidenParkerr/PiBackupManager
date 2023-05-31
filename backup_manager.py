import configparser
import argparse
import subprocess
import requests
import logging
import os


class BackupManager:
    def __init__(self, backup_file) -> None:
        self.backup_file = "/export/1TB/plexserver-backup/backup.img"
        self.backup_file = backup_file
        self.backup_command = f"sudo dd if=/dev/mmcblk0 of={self.backup_file} bs=1M"
        self._init_logger()
        self.load_telegram_config()
        self.lock_file = "/tmp/backup_manager.lock"

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
        console_handler.setLevel(logging.DEBUG)

        file_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        console_format = logging.Formatter(
            '%(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(file_format)
        console_handler.setFormatter(console_format)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def load_telegram_config(self):
        self.logger.info("Loading Telegram bot token and chat ID...")
        
        config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")
        config.read(config_path)

        self.bot_token = config['Telegram']['bot_token'].strip('"')
        self.chat_id = config['Telegram']['chat_id'].strip('"')

        if self.bot_token is None or self.chat_id is None:
            self.logger.critical(
                "Telegram bot token or chat ID not found. Exiting...")
            exit(1)
        self.logger.info("Telegram bot token and chat ID loaded.")

    def send_notification(self, body: str) -> None:
        try:
            tg_api_link = f"https://api.telegram.org/bot{self.bot_token}/sendMessage?chat_id={self.chat_id}&parse_mode=Markdown&text={body}"
            self.logger.info(f"Sending HTTP request to Telegram API...")
            response = requests.get(tg_api_link)
            if response.status_code == 200:
                self.logger.info("Notification sent to Telegram.")
            else:
                self.logger.error(
                    f"Failed to send notification to Telegram, status code: {response.status_code}")
        except Exception as e:
            self.logger.error("Failed to send notification to Telegram", exc_info=True)

    def run_backup(self, device_name: str = "device1"):
        if os.path.exists(self.lock_file):
            self.logger.error("An Instance of `backup_manager` is already running. Exiting...")
            return

        with open(self.lock_file, 'w') as file:
            file.write("lock")

        try:    
            markdown_message = f"*Backup Started for _{device_name}_ ...*"
            self.logger.info(f"Backup Started for {device_name}...")
            self.send_notification(markdown_message)

            error_thrown = False
            try:
                self.logger.info("Running backup command...")
                self.execute_backup_and_zip()
                self.send_notification("*Backup and compression finished successfully.*")
            except KeyboardInterrupt:
                self.logger.error("Backup process interrupted by keyboard.")
                self.send_notification("*Backup process interrupted by keyboard.*")
                error_thrown = True
            except Exception as e: 
                self.handle_error(e)
                error_thrown = True
            finally:
                self.cleanup(error_thrown)
        finally:
            os.remove(self.lock_file)


    def execute_backup_and_zip(self):
        subprocess.check_output(self.backup_command, shell=True, stderr=subprocess.STDOUT)
        self.logger.info("Backup process completed. Attempting to gzip the backup image...")
        self.send_notification("Backup process completed. Attempting to gzip the backup image...")
        gzip_command = f"gzip -c {self.backup_file}"
        subprocess.check_output(gzip_command, shell=True, stderr=subprocess.STDOUT)
        self.logger.info("Backup image compressed successfully. Sending notification to Telegram...")

    def handle_error(self, e):
        if isinstance(e, subprocess.CalledProcessError):
            self.logger.error("Backup or compression process failed.")
            error_message = f"Backup or compression process failed with error: {e.output.decode()}"
            self.send_notification(error_message)
        else:
            self.logger.error(f"Unexpected error: {e}")
            self.send_notification(f"Backup failed due to an unexpected error: {e}")


    def cleanup(self, error_thrown: bool):
        if error_thrown and os.path.exists(self.backup_file):
            try:
                os.remove(self.backup_file)
                self.logger.info("Incomplete backup file deleted.")
            except Exception as e:
                self.logger.error(f"Failed to delete incomplete backup file. Error: {e}", exc_info=True)
        
        if error_thrown:
            self.send_notification("*Incomplete backup process cleaned up.*")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup Manager")
    parser.add_argument("backup_file", help="Backup image location")

    args = parser.parse_args()

    backup_manager = BackupManager(args.backup_file)
    backup_manager.run_backup("PlexServer")
