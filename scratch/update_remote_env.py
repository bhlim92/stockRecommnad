from paramiko import SSHClient, AutoAddPolicy

def update_remote_env():
    host = "bhlim123.cafe24.com"
    port = 22
    username = "root"
    password = "!monk9203!"
    
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    ssh.connect(host, port=port, username=username, password=password)
    
    # 1. Read remote .env file
    print("Reading remote .env file...")
    stdin, stdout, stderr = ssh.exec_command("cat /root/stockRecommnad/.env")
    env_content = stdout.read().decode()
    
    # 2. Check if database variables are already defined
    db_config_lines = [
        "DB_TYPE=mariadb",
        "DB_HOST=127.0.0.1",
        "DB_PORT=3306",
        "DB_USER=root",
        "DB_PASSWORD=cbm",
        "DB_NAME=stock_db"
    ]
    
    has_db_config = "DB_TYPE=" in env_content
    
    if has_db_config:
        print("Database config is already present in remote .env. Cleaning up existing DB config lines...")
        # Remove any existing DB config lines to avoid duplicates
        clean_cmd = "sed -i '/DB_TYPE=/d; /DB_HOST=/d; /DB_PORT=/d; /DB_USER=/d; /DB_PASSWORD=/d; /DB_NAME=/d' /root/stockRecommnad/.env"
        ssh.exec_command(clean_cmd)
        
    print("Appending new Database configuration to remote .env...")
    append_content = "\n" + "\n".join(db_config_lines) + "\n"
    # Write to a temp file and append it
    ssh.exec_command(f"echo '{append_content}' >> /root/stockRecommnad/.env")
    
    # 3. Print updated .env (excluding sensitive API key values for display)
    stdin, stdout, stderr = ssh.exec_command("cat /root/stockRecommnad/.env")
    updated_env = stdout.read().decode()
    print("\nUpdated remote .env file (first 400 chars):")
    print(updated_env[:400])
    
    # 4. Restart the fastapi service if it runs as systemd
    print("\nRestarting stock-recommnad/fastapi service on the remote server to apply changes...")
    ssh.exec_command("systemctl restart stock-recommnad || systemctl restart fastapi || pm2 restart all || killall uvicorn")
    
    ssh.close()
    print("Remote environment update and service restart completed.")

if __name__ == "__main__":
    update_remote_env()
