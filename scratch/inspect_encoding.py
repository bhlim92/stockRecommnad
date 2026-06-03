import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from app.config import AppConfig

def inspect_encoding():
    scopes = ["https://www.googleapis.com/auth/drive"]
    token_json_str = AppConfig.GOOGLE_DRIVE_TOKEN_JSON
    creds_info = json.loads(token_json_str)
    creds = Credentials.from_authorized_user_info(creds_info, scopes=scopes)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        
    drive_service = build("drive", "v3", credentials=creds)
    export_bytes = drive_service.files().export(
        fileId="19Gtw2QutX6xChSDanqd79edD3WFYVqooeRiHsK8pGdI",
        mimeType="text/csv"
    ).execute()
    
    # Try decoding using utf-8 first
    try:
        decoded_utf8 = export_bytes.decode("utf-8")
        print("Decoded as UTF-8 successfully.")
        lines = decoded_utf8.splitlines()
        print("Header Row UTF-8:")
        print(lines[0])
    except Exception as e:
        print("UTF-8 decoding failed:", str(e))
        
    # Try decoding using cp949
    try:
        decoded_cp949 = export_bytes.decode("cp949")
        print("\nDecoded as CP949 successfully.")
        lines_cp949 = decoded_cp949.splitlines()
        print("Header Row CP949:")
        print(lines_cp949[0])
    except Exception as e:
        print("CP949 decoding failed:", str(e))

if __name__ == "__main__":
    inspect_encoding()
