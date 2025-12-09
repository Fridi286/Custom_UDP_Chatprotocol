import subprocess
import sys
import time


def open_terminal(command: str):
    # /k = Fenster bleibt offen
    subprocess.Popen(f'start cmd.exe /k "{command}"', shell=True)


def main():
    VENV_PYTHON = r"C:\Users\fridi\PycharmProjects\CustomNetworkRN\.venv\Scripts\python.exe"

    open_terminal(f"{VENV_PYTHON} -m customSocket.mySocket 10.8.3.3 3001")
    time.sleep(0.3)

    open_terminal(f"{VENV_PYTHON} -m customSocket.mySocket 10.8.3.3 3002")
    time.sleep(0.3)

    #open_terminal(f"{VENV_PYTHON} -m customSocket.mySocket 127.0.0.1 3003")
    time.sleep(0.3)

if __name__ == "__main__":
    main()
    while True:
        time.sleep(1)
