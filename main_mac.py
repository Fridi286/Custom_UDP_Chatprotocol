import subprocess
import time
import os


def open_terminal(command: str):
    project_path = "/Users/fridi/PycharmProjects/Custom_UDP_Chatprotocol"
    apple_script = f'''
    tell application "Terminal"
        do script "cd {project_path}; {command}"
        activate
    end tell
    '''
    subprocess.Popen(["osascript", "-e", apple_script])


def main():
    # Pfad zur Python-Version im venv
    VENV_PYTHON = "/Users/fridi/PycharmProjects/Custom_UDP_Chatprotocol/.venv/bin/python"

    open_terminal(f'{VENV_PYTHON} -m customSocket.mySocket 10.8.3.3 3001')
    time.sleep(0.3)

    open_terminal(f'{VENV_PYTHON} -m customSocket.mySocket 10.8.3.3 3002')
    time.sleep(0.3)

    #open_terminal(f'{VENV_PYTHON} -m customSocket.mySocket 127.0.0.1 3003')
    time.sleep(0.3)


if __name__ == "__main__":
    main()
    while True:
        time.sleep(1)