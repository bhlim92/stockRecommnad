import os
from paramiko import SSHClient, AutoAddPolicy

def read_remote_log():
    host = "bhlim123.cafe24.com"
    port = 22
    username = "root"
    password = "!monk9203!"
    
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    
    print(f"Connecting to {host}:{port}...")
    ssh.connect(host, port=port, username=username, password=password)
    
    cmd = "tail -n 100 /root/stockRecommnad/logs/scheduler.log"
    print(f"Running command: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    
    ssh.close()

if __name__ == "__main__":
    read_remote_log()
