import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

def main():
    scopes = ["https://www.googleapis.com/auth/drive"]
    credentials_path = "config/credentials.json"
    token_path = "config/token.json"
    
    if not os.path.exists("config"):
        os.makedirs("config")
        
    if not os.path.exists(credentials_path):
        print(f"[x] Error: OAuth Client Credentials file not found at: {credentials_path}")
        print("Please follow these steps to obtain it:")
        print("1. Go to Google Cloud Console (https://console.cloud.google.com/)")
        print("2. Navigate to 'APIs & Services' -> 'Credentials'")
        print("3. Click 'Create Credentials' -> 'OAuth client ID'")
        print("4. Select Application Type: 'Desktop App' and name it, then click Create.")
        print("5. Download the JSON file for the created credentials client.")
        print(f"6. Rename it to 'credentials.json' and place it inside the 'config/' directory.")
        return
        
    print("[*] Starting Google OAuth2 authorization flow...")
    print("[*] Your web browser will open shortly to log into your Google Account.")
    try:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
        # Run local server to capture the redirect code
        creds = flow.run_local_server(port=0)
        
        # Save token to file
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
            
        print("\n" + "="*80)
        print("[+] SUCCESS! User OAuth2 Token generated and saved successfully!")
        print(f"    File path: {token_path}")
        print("="*80)
        print("\nCopy the ENTIRE JSON block below (including the curly braces {}):")
        print("Use this content for your GOOGLE_DRIVE_TOKEN_JSON environment variable or GitHub Secrets.\n")
        print(creds.to_json())
        print("\n" + "="*80 + "\n")
        
    except Exception as e:
        print(f"[x] Authorization failed: {str(e)}")

if __name__ == "__main__":
    main()
