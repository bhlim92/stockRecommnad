from paramiko import SSHClient, AutoAddPolicy

def allow_remote():
    host = "bhlim123.cafe24.com"
    port = 22
    username = "root"
    password = "!monk9203!"
    
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    ssh.connect(host, port=port, username=username, password=password)
    
    # Run the SQL command with password authentication
    cmd = "mysql -u root -pcbm -e \"CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY 'cbm'; GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION; FLUSH PRIVILEGES;\""
    print(f"Running command: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    exit_status = stdout.channel.recv_exit_status()
    print(f"Exit status: {exit_status}")
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(f"Stdout:\n{out}")
    if err:
        print(f"Stderr:\n{err}")
        
    ssh.close()

if __name__ == "__main__":
    allow_remote()
