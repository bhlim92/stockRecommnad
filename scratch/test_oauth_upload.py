import os
import sys
from dotenv import load_dotenv

sys.path.append("c:\\Users\\samsung\\proj\\stockRecommnad")
from app.gdrive_uploader import GoogleDriveUploader

def test_oauth_upload():
    load_dotenv("c:\\Users\\samsung\\proj\\stockRecommnad\\.env")
    token_json = os.getenv("GOOGLE_DRIVE_TOKEN_JSON")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    
    print(f"[*] OAuth Token JSON configured: {bool(token_json)}")
    print(f"[*] Target Folder ID: {folder_id}")
    
    if not token_json:
        print("[x] Error: GOOGLE_DRIVE_TOKEN_JSON not found in .env")
        return
        
    try:
        # Initialize with token_json_str
        uploader = GoogleDriveUploader(token_json_str=token_json)
        uploader.authenticate()
        print("[+] Authentication Successful using User OAuth2 Token!")
        
        # Test creating a temporary file and uploading
        temp_file = "test_oauth_upload.md"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write("# OAuth2 Upload Test\nThis is a non-empty file to test Google Drive user account quota.")
            
        print("[*] Uploading file to Google Drive...")
        web_link = uploader.upload_markdown_file(
            local_path=temp_file,
            filename=temp_file,
            folder_id=folder_id
        )
        print(f"[+] SUCCESS! File uploaded to Google Drive.")
        print(f"[+] Web Link: {web_link}")
        
        # Cleanup
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
    except Exception as e:
        print(f"[x] Upload failed: {str(e)}")

if __name__ == "__main__":
    test_oauth_upload()
