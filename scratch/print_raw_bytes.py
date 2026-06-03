import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from app.config import AppConfig

def print_raw():
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
    
    print("Raw bytes slice (first 100):", export_bytes[:100])
    
    # Check if there is any 'SK하이닉스' in the bytes decoded differently
    # Let's search for the ticker 000660.ks in the CSV
    lines = export_bytes.split(b'\n')
    for line in lines:
        if b'000660' in line:
            print("Raw 000660 line:", line)

if __name__ == "__main__":
    print_raw()
