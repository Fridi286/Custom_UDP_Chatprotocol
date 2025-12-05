import subprocess
import time

def open_terminal(command: str):
    # /k = Fenster bleibt offen
    subprocess.Popen(f'start cmd.exe /k "{command}"', shell=True)

def main():
    open_terminal("python mySocket.py 127.0.0.1 3001")
    time.sleep(0.3)

    open_terminal("python mySocket.py 127.0.0.1 3002")
    time.sleep(0.3)

    open_terminal("python mySocket.py 127.0.0.1 3003")
    time.sleep(0.3)

if __name__ == "__main__":
    main()