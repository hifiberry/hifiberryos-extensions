#!/usr/bin/env python3

import configparser
import logging
import argparse
import sys
import subprocess
import os
import shutil
import glob

EXTENSION_DIR="/data/extensions"
BEOCREATE_EXTENSION_DIR="/opt/beocreate/beo-extensions"

CMD_STATUS="status"
CMD_INSTALL="install"

config = None


def extension_dir(extension_name):
    return EXTENSION_DIR+"/"+extension_name

def active_file(extension):
    return extension_dir(extension)+"/is_active"

def activate_extension(extension, activate=True):
    filename = active_file(extension)

    if activate:
        try:
            with open(filename, 'w'):
                pass
        except Exception as e:
                print("can't create "+filename)
                sys.exit(1)
    else:
        try:
            os.remove(filename)
        except OSError as e:
            pass

def is_activated(extension):
    return os.path.exists(active_file(extension))


def check_dockercompose(extension):
    if not (os.path.exists(extension_dir(extension)+"/docker-compose.yaml")):
        print("can't start extension, no docker-compose.yaml")
        sys.exit(1)

def check_extension_exists(extension):
    if not(directory_exists(extension_dir(extension))):
        print("extension "+extension+ " doesn't exist")
        sys.exit(1)

def directory_exists(directory):
    if os.path.exists(directory) and os.path.isdir(directory):
        return True
    else:
        return False

def run_command_in_directory(command, directory):
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        return result.returncode, result.stdout
    except Exception as e:
        return "", -1

def read_config(filename):
    global config
    config = configparser.ConfigParser()
    config.read(filename)


def install_extension(extension):
    mydir = extension_dir(extension)
    if (directory_exists(mydir)):
        print("extension "+extension+ " already installed")
        sys.exit(1)

    os.makedirs(mydir, exist_ok=True)

    cfg = config[extension]
    repo = cfg.get("repository")
    if repo is None:
        print("git repository missing for extension "+extension)
        sys.exit(1)

    branch = cfg.get("branch")

    # Build git clone command
    cmd = "git clone "
    if branch is not None:
        cmd = cmd + "--branch "+branch+" "
    cmd = cmd+repo+" ."

    retcode, output = run_command_in_directory(cmd,mydir)
    if (retcode):
        print("Failed cloning git repository: ")
        print(output)
        sys.exit(1)

    print("got extension via git")

    link_beocreate_extension(extension)

    return True


def uninstall_extension(extension):
    check_extension_exists(extension)

    unlink_beocreate_extension(extension)

    try:
        shutil.rmtree(extension_dir(extension))
        print("removed "+extension_dir(extension))
    except Exception as e:
        print("Failed to remove extension directory for "+extension)
        sys.exit(1)



def update_extension(extension):
    check_extension_exists(extension)

    cmd = "git pull"
    
    retcode, output = run_command_in_directory(cmd,extension_dir(extension))
    if (retcode):
        print("failed updating via git")
        print(output)
        sys.exit(1)

    print("updated via git")

    link_beocreate_extension(extension)


def start_extension(extension, exit_on_fail=True, activate=True):
    check_extension_exists(extension)
    check_dockercompose(extension)

    cmd="docker-compose up -d"
    retcode, output = run_command_in_directory(cmd,extension_dir(extension))
    if (retcode):
        print("failed to start docker containers for extension "+extension)
        if exit_on_fail:
            print(output)
            sys.exit(1)

    else:
        if activate:
            activate_extension(extension, True)



def link_beocreate_extension(extension):
    directory_path = extension_dir(extension)+"/beo-extensions/*/"
    directories = glob.glob(directory_path)
    directories = [d.rstrip('/') for d in directories]
    for d in directories:
        dst = BEOCREATE_EXTENSION_DIR+"/"+os.path.basename(d)
        try:
            os.symlink(d, dst)
            print("link "+d+" to "+dst)

        except:
            print("couldn't link "+d+" to "+dst+", ignoring")


def unlink_beocreate_extension(extension):
    mydir=extension_dir(extension)
    for f in os.listdir(BEOCREATE_EXTENSION_DIR):
        f = os.path.join(BEOCREATE_EXTENSION_DIR, f)
        if os.path.islink(f):
            target_path = os.path.realpath(f)
            if target_path.startswith(mydir):
                try:
                    os.remove(f)
                    print("removed symlink "+f)
                except Exception as e:
                    print("couldn't unlink "+f+", ignoring")
       

def stop_extension(extension, exit_on_fail=True, deactivate=True):
    check_dockercompose(extension)
    mydir = extension_dir(extension)

    cmd="docker-compose stop"
    retcode, output = run_command_in_directory(cmd,mydir)
    if (retcode):
        print("failed to stop docker containers for extension "+extension)
        if exit_on_fail:
            print(output)
            sys.exit(1)

    if deactivate:
        activate_extension(extension, False)


def is_docker_running(extension):
    cmd="docker-compose ls| wc -l"
    retcode, output = run_command_in_directory(cmd,extension_dir(extension))
    try:
        count=int(output.strip())
    except:
        count=0

    if (count>1):
        return True
    else:
        return False


def status(extension):
    mydir = extension_dir(extension)
    if not directory_exists(mydir):
        print("extension "+extension+ " does not exist")
        sys.exit(1)

    if (is_docker_running(extension)):
        print("running")
    else:
        print("not running")


def start_all():
    for extension in config:
        if extension=="DEFAULT":
            continue

        if is_activated(extension):
            start_extension(extension,exit_on_fail=False)


def shutdown_all():
    for extension in config:
        if extension=="DEFAULT":
            continue

        stop_extension(extension,exit_on_fail=False, deactivate=False)

def status_all():
    for extension in config:
        if extension=="DEFAULT":
            continue

        mydir = extension_dir(extension)
        if not directory_exists(mydir):
            state="not installed"
        else:
            if (is_docker_running(extension)):
                state="running"
            else:
                state="not running"

        print(extension,": ",state)
        

def run_command(args):

    if args.extension is not None and args.extension not in config:
        print("extension "+args.extension+ " unknown")
        sys.exit(1)

    error = False

    if args.command == "status":
        if (args.extension is not None):
            status(args.extension)
        else:
            status_all()
    elif args.command == "install":
        install_extension(args.extension)
    elif args.command in ["uninstall","remove"]:
        uninstall_extension(args.extension)
    elif args.command == "update":
        update_extension(args.extension)
    elif args.command == "start":
        start_extension(args.extension)
    elif args.command == "stop":
        stop_extension(args.extension)
    elif args.command == "startup":
        start_all()
    elif args.command == "shutdown":
        shutdown_all()

    else:
        logging.error("Command "+args.command+" unknown.")
        sys.exit(1)

    if (error):
        sys.exit(1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_file", default="/etc/extensions.conf", help="Path to the configuration file")
    parser.add_argument("command", nargs="?", default = "status", help="Name of the command")
    parser.add_argument("extension", nargs="?", default=None, help="Optional name of the extension")
    args = parser.parse_args()

    read_config(args.config_file)
    run_command(args)

