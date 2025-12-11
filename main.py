import socket
import subprocess
import sys
import time
import platform



def open_terminal_win(command: str):
    # /k = Fenster bleibt offen
    subprocess.Popen(f'start cmd.exe /k "{command}"', shell=True)

def open_terminal_mac(command: str):
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
    VENV_PYTHON = "C:\\Users\\fridi\\PycharmProjects\\CustomNetworkRN\\.venv\\Scripts\\python.exe"

    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    if platform.system() == "Windows":
        VENV_PYTHON = "C:\\Users\\fridi\\PycharmProjects\\CustomNetworkRN\\.venv\\Scripts\\python.exe"
        open_terminal=open_terminal_win
        print("Running on Windows")
    elif platform.system() == "Darwin":
        VENV_PYTHON = "/Users/fridi/PycharmProjects/Custom_UDP_Chatprotocol/.venv/bin/python"
        open_terminal=open_terminal_mac
        print("Running on macOS")

    ip = local_ip

    for i in range(3000, 3002):
        open_terminal(f'{VENV_PYTHON} -m customSocket.mySocket {ip} {i}')
        time.sleep(0.01)

if __name__ == "__main__":
    main()
    while True:
        time.sleep(1)
