import sys
import subprocess
from paramiko import SSHClient, AutoAddPolicy

def install_mariadb():
    host = "bhlim123.cafe24.com"
    port = 22
    username = "root"
    password = "!monk9203!"
    
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    
    print(f"Connecting to {host}:{port} as {username}...")
    ssh.connect(host, port=port, username=username, password=password)
    print("Connected successfully.")
    
    commands = [
        # 1. Update package list and install MariaDB server & client
        "apt-get update",
        "apt-get install -y mariadb-server mariadb-client",
        
        # 2. Make sure MariaDB service is enabled and running
        "systemctl enable mariadb",
        "systemctl start mariadb",
        
        # 3. Set root password for localhost connections
        "mysql -e \"ALTER USER 'root'@'localhost' IDENTIFIED BY 'cbm'; FLUSH PRIVILEGES;\"",
        
        # 4. Create and authorize root user for remote connections (any host '%') with password 'cbm'
        "mysql -e \"CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY 'cbm'; GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION; FLUSH PRIVILEGES;\"",
        
        # 5. Modify MariaDB configuration to bind to all interfaces (0.0.0.0) instead of localhost only
        "sed -i 's/bind-address\\s*=\\s*127.0.0.1/bind-address = 0.0.0.0/g' /etc/mysql/mariadb.conf.d/50-server.cnf || sed -i 's/bind-address\\s*=\\s*127.0.0.1/bind-address = 0.0.0.0/g' /etc/mysql/my.cnf",
        
        # 6. Restart MariaDB to apply configuration changes
        "systemctl restart mariadb || systemctl restart mysql",
        
        # 7. Create the stock database if it doesn't exist
        "mysql -u root -pcbm -e \"CREATE DATABASE IF NOT EXISTS stock_db;\"",
        
        # 8. Verify installation and check listening ports
        "mysql -u root -pcbm -e \"SHOW DATABASES;\"",
        "netstat -tulnp | grep mysql || ss -tulnp | grep 3306"
    ]
    
    for cmd in commands:
        print(f"\n[REMOTE CMD] Running: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        
        # Wait for the command to finish and get exit code
        exit_status = stdout.channel.recv_exit_status()
        print(f"Exit status: {exit_status}")
        
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out:
            print(f"Stdout:\n{out}")
        if err:
            print(f"Stderr:\n{err}")
            
    ssh.close()
    print("\nMariaDB installation and configuration script finished.")

if __name__ == "__main__":
    install_mariadb()
