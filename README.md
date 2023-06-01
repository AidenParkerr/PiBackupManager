    
    
    
    
    
    
# Backup Manager

The Backup Manager is a Python script that automates the process of backing up a device (such as a Raspberry Pi's SD card). This script utilizes the Telegram API to send notifications about the backup process, making it easier to monitor its progress and status.## Features

## Features

- Automatically backs up a specified device.
- Compresses the backup image using gzip.
- Logs the backup process, with logs stored in backup_manager.log.
- Prevents simultaneous runs of the script by using a lock file mechanism.
- Sends notifications about the backup process via Telegram.
- Uses a timeout for the backup and compression processes to prevent hanging indefinitely.
- Cleans up and deletes incomplete backup files in case of errors.
- Allows for the specification of backup file location, config file location, device name, and timeout when running the script.

## Requirements

The script requires Python 3 and the following Python packages:
- `configparser`
- `argparse`
- `subprocess`
- `requests`
- `logging`
- `os`

These packages are included in the standard Python 3 library.

## Configuration

You need to create a `config.ini` file in the same directory as the script or specify the path to it when running the script. This file should contain your Telegram bot token and chat ID in the following format:
```
[Telegram]
bot_token = "your_bot_token"
chat_id = "your_chat_id"
```

Please note that the `config.ini` file should not be shared or uploaded to public repositories as it contains sensitive data.

## Usage

You can run the script with the following command:

```
python3 backup_manager.py --backup_file <backup file path> --config_file <config file path> --device_name <device name> --timeout <timeout in seconds>
```

The default device name for notifications is "PlexServer". If you want to use a different device name, you can change the argument in the `run_backup` function at the bottom of the script.


The arguments are as follows:

- `backup_file`: The path to the location where the backup file will be stored.
- `config_file`: The path to the configuration file (config.ini).
- `device_name`: The name of the device being backed up.
- `timeout`: The timeout for the backup and compression processes in seconds.

If any arguments are not provided, the script will use default values (excluding `backup_file` and `config_file`). The default device name is "device1", and the default timeout is 3600 seconds (1 hour).

