import json
import csv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from app.config import AppConfig

def map_headers():
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
    
    decoded = export_bytes.decode("utf-8")
    lines = decoded.splitlines()
    reader = csv.reader(lines)
    rows = list(reader)
    
    header = rows[0]
    print("Headers and indices:")
    for idx, h in enumerate(header):
        print(f"  {idx}: {h}")
        
    print("\nRow 14 (Hynix) mapped:")
    row_14 = rows[13] # Row 14 is index 13 in list
    for idx, (h, val) in enumerate(zip(header, row_14)):
        print(f"  {idx} [{h}]: {val}")

if __name__ == "__main__":
    map_headers()
