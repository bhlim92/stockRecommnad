import os
from paramiko import SSHClient, AutoAddPolicy

def check_processes():
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
        "ps aux | grep -E 'python|uvicorn|fastapi|main|web_server'",
        "netstat -tulnp | grep -E 'python|uvicorn|8000|80'",
        "pm2 list || true",
        "systemctl status stock-recommnad || systemctl status fastapi || true"
    ]
    
    for cmd in commands:
        print(f"\nRunning remote command: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        if out:
            print(f"Stdout:\n{out}")
        if err:
            print(f"Stderr:\n{err}")
            
    ssh.close()

if __name__ == "__main__":
    check_processes()
