# Backup Manager

The Backup Manager is a Python script that automates the process of backing up your Raspberry Pi's SD card. This script also utilizes the Telegram API to send notifications about the backup process.

## Features

- Automatically backs up the entire SD card.
- Compresses the backup image using `gzip`.
- Logs the backup process, logging can be viewed in `backup_manager.log`.
- Prevents simultaneous runs of the script by using a lock file mechanism.
- Sends notifications about the backup process via Telegram.

## Requirements

The script requires the following Python packages:
- `configparser`
- `argparse`
- `subprocess`
- `requests`
- `logging`
- `os`

These packages are included in the standard Python 3 library.

## Configuration

You need to create a `config.ini` file in the same directory as the script. This file should contain your Telegram bot token and chat ID in the following format:

```
[Telegram]
bot_token = "your_bot_token"
chat_id = "your_chat_id"
```


Please note that the `config.ini` file should not be shared or uploaded to public repositories as it contains sensitive data.

## Usage

You can run the script with the following command:

```
python3 backup_manager.py
```

The default device name for notifications is "PlexServer". If you want to use a different device name, you can change the argument in the `run_backup` function at the bottom of the script.






