# sync_config

This script was written to sync the configuration files of a linux server to a
git repository. It is intended to be used with a remote server and runned as a
cron job. It is not made to sync your laptop configuration files, but you can
do pretty much what you want with it.

# Usage

Create a python virtual environment and install the requirements. Then run the 
script.
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 sync.py
```
After creating the virtual environment, you can also run the script with the 
following command:
```bash
./venv/bin/python3 sync.py
```
This will run the script with all the required dependencies but without the
need to activate the virtual environment.
