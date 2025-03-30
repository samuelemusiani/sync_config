#!/usr/bin/env python3

# Change the following variables to match your configuration
GIT_REPO_URL="" # URL should be https://...
GIT_TOKEN=""
REPO_PATH="/root/sync-script" # Local path where the repo will be cloned

# You can use a telegram bot to send notifications when the script updates the 
# repo
TELEGRAM_BOT_TOKEN=""
CHAT_ID=""

# This is the name and email that will be used to commit changes
COMMIT_NAME="Script sync"
COMMIT_EMAIL="sync@mail.invalid"

import sys
import yaml
import git
import os
import shutil
import telegram
import socket
import asyncio
import re

README = "# THIS REPO IS MANAGED BY A SCRIPT\n"
REPO_WITH_TOKEN=GIT_REPO_URL[:8] + GIT_TOKEN + '@' + GIT_REPO_URL[8:]

def init_repo():
    print(f'Cloning repo')
    repo = git.Repo.clone_from(REPO_WITH_TOKEN, REPO_PATH)

    with repo.config_writer() as cw:
        cw.set_value("user", "name", COMMIT_NAME)
        cw.set_value("user", "email", COMMIT_EMAIL)

    # If the repo is empty, create a README file
    if len(repo.heads) == 0:
        print(f'Cloned empty repo. Initializing README')
        with open(os.path.join(REPO_PATH, 'README.md'), 'w') as f:
            f.write(README)


        repo.index.add(['README.md'])
        repo.index.commit('Initial commit')

        origin = repo.remotes.origin

        origin.push('main')
    else:
        print(f'Repo is not empty. Checking README')
        need_commit = False
        with open(os.path.join(REPO_PATH, 'README.md'), 'r+') as f:
            content = f.read()
            if content.find(README) == -1:
                print(f'Updating README')
                f.seek(0, 0)
                f.write(README + content)

                need_commit = True

        if need_commit:
            repo.index.add(['README.md'])
            repo.index.commit('Update README.md')
            origin = repo.remotes.origin
            origin.push('main')

    return repo

def pull_repo(repo):
    try:
        repo.remotes.origin.pull()
    except git.exc.GitCommandError as e:
        print(f"Error pulling repo: {e}")
        sys.exit(1)

def repo_push(repo):
    try:
        repo.remotes.origin.push()
    except git.exc.GitCommandError as e:
        print(f"Error pushing repo: {e}")
        sys.exit(1)

def backup_dir(dir, repo):
    src_path = dir['path']
    dest_path = os.path.join(REPO_PATH, dir['repo_path'])
    exclude = dir.get('exclude', [])
    print(f'Backing up {src_path} into {dest_path}')

    if not os.path.exists(src_path):
        print(f"Path {src_path} does not exist")
        return

    if not os.path.exists(dest_path):
        os.makedirs(dest_path)

    for root, dirs, files in os.walk(src_path):
        for f in files:
            src_file = os.path.join(root, f)

            if src_file in exclude:
                continue

            # We must preserve the directory structure in the repo
            rel_dest_file = os.path.relpath(os.path.join(root, f), src_path)
            dest_file = os.path.join(REPO_PATH, dest_path, rel_dest_file)

            dest_dir = os.path.dirname(dest_file)
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)

            print(f"Copying file {dest_file}")
            shutil.copy(src_file, dest_file)
            repo.index.add([dest_file])

def force_ipv4_socket():
    socket.getaddrinfo = lambda *args, **kwargs: [
        addr for addr in socket._socket.getaddrinfo(*args, **kwargs)
        if addr[0] == socket.AF_INET  # Only keep IPv4 addresses
    ]


def send_telegram_message(message, commit):
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

    m_formatted = f"""
*Config sync notification*\\
A configuration update has been saved\.\\
Commit: [{commit[:7]}]({re.escape(GIT_REPO_URL)}/commit/{commit})\\
*Details:*\\
```
{message}
```
"""

    print(m_formatted)

    asyncio.run(bot.send_message(
        chat_id=CHAT_ID, 
        text=m_formatted,
        parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
    ))


def main():
    if len(sys.argv) < 2:
        print("Usage: update.py <config_path>")
        sys.exit(1)
    config_path = sys.argv[1]

    #print(f'Config path: {config_path}')

    with open(config_path, 'r') as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"Error reading config file: {e}")
            sys.exit(1)

    #print(config)

    # For telegram to work, we need to force the socket to use ipv4
    force_ipv4_socket()

    if not os.path.exists(REPO_PATH):
        repo = init_repo()
    else:
        repo = git.Repo(REPO_PATH)

    with repo.config_writer() as cw:
        cw.set_value("user", "name", COMMIT_NAME)
        cw.set_value("user", "email", COMMIT_EMAIL)

    pull_repo(repo)

    for d in config['dirs']:
        backup_dir(d, repo)

    diff = repo.git.diff("--cached")

    if not diff:
        print("No changes detected")
        sys.exit(0)

    commit = repo.index.commit("Script sync")

    repo_push(repo)

    send_telegram_message(diff, commit.hexsha)

if __name__ == "__main__":
    main()
