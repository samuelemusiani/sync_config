#!/usr/bin/env python3

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


def init_repo(repo_url, token, repo_path, commit_name, commit_email):
    print('Cloning repo')

    repo_with_token = repo_url[:8] + token + '@' + repo_url[8:]

    repo = git.Repo.clone_from(repo_with_token, repo_path)

    with repo.config_writer() as cw:
        cw.set_value("user", "name", commit_name)
        cw.set_value("user", "email", commit_email)

    # If the repo is empty, create a README file
    if len(repo.heads) == 0:
        print('Cloned empty repo. Initializing README')
        with open(os.path.join(repo_path, 'README.md'), 'w') as f:
            f.write(README)

        repo.index.add(['README.md'])
        repo.index.commit('Initial commit')

        origin = repo.remotes.origin

        origin.push('main')
    else:
        print('Repo is not empty. Checking README')
        need_commit = False
        with open(os.path.join(repo_path, 'README.md'), 'r+') as f:
            content = f.read()
            if content.find(README) == -1:
                print('Updating README')
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


def backup_dir(dir, repo, repo_path):
    src_path = dir['path']
    dest_path = os.path.join(repo_path, dir['repo_path'])
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
            dest_file = os.path.join(repo_path, dest_path, rel_dest_file)

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


def send_telegram_message(token, chat_id, message, commit, repo_url):
    bot = telegram.Bot(token=token)

    m_formatted = f"""
*Config sync notification*\\
A configuration update has been saved\.\\
Commit: [{commit[:7]}]({re.escape(repo_url)}/commit/{commit})\\
*Details:*\\
```
{message}
```
"""

    print(m_formatted)

    asyncio.run(bot.send_message(
        chat_id=chat_id,
        text=m_formatted,
        parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
    ))


def main():
    if len(sys.argv) < 2:
        print("Usage: update.py <config_path>")
        sys.exit(1)
    config_path = sys.argv[1]

    # print(f'Config path: {config_path}')

    with open(config_path, 'r') as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"Error reading config file: {e}")
            sys.exit(1)

    # print(config)

    # For telegram to work, we need to force the socket to use ipv4
    force_ipv4_socket()

    if not os.path.exists(config.globals.git.path):
        cg = config.globals.git
        repo = init_repo(cg.url, cg.token, cg.path,
                         cg.commit.name, cg.commit.email)
    else:
        repo = git.Repo(config.globals.git.path)

    with repo.config_writer() as cw:
        cw.set_value("user", "name", config.globals.git.commit.name)
        cw.set_value("user", "email", config.globals.git.commit.email)

    pull_repo(repo)

    for d in config['dirs']:
        backup_dir(d, repo, config.globals.git.path)

    diff = repo.git.diff("--cached")

    if not diff:
        print("No changes detected")
        sys.exit(0)

    commit = repo.index.commit("Script sync")

    repo_push(repo)

    send_telegram_message(config.globals.telegram.token,
                          config.globals.telegram.chat_id, diff, commit.hexsha,
                          config.globals.git.url)


if __name__ == "__main__":
    main()
