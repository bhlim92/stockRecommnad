import os
import sys
import subprocess

try:
    import paramiko
except ImportError:
    print("[*] Installing paramiko library for SSH...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko"])
    import paramiko

from paramiko import SSHClient, AutoAddPolicy

def run_remote_commands():
    host = "bhlim123.cafe24.com"
    port = 22
    username = "root"
    password = "!monk9203!"
    
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    
    print(f"Connecting to {host}:{port} as {username}...")
    ssh.connect(host, port=port, username=username, password=password)
    print("Connected.")
    
    commands = [
        "apt-get update && apt-get install -y python3-pip python3-venv",
        # recreate venv
        "rm -rf /root/stockRecommnad/venv",
        "python3 -m venv /root/stockRecommnad/venv",
        # install pip if still missing
        "curl -sS https://bootstrap.pypa.io/get-pip.py | /root/stockRecommnad/venv/bin/python3 || true",
        # install requirements
        "/root/stockRecommnad/venv/bin/pip install --upgrade pip",
        "/root/stockRecommnad/venv/bin/pip install -r /root/stockRecommnad/requirements.txt",
        # run pipeline to verify
        "cd /root/stockRecommnad && ./run_pipeline.sh"
    ]
    
    for cmd in commands:
        print(f"\nRunning command: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        print(f"Exit status: {exit_status}")
        out = stdout.read().decode()
        err = stderr.read().decode()
        if out:
            print(f"Stdout:\n{out}")
        if err:
            print(f"Stderr:\n{err}")

    ssh.close()

if __name__ == "__main__":
    run_remote_commands()
