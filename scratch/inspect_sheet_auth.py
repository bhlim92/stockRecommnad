import os
import json
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from app.config import AppConfig

def test_sheet_access():
    scopes = [
        "https://www.googleapis.com/auth/drive"
    ]
    
    token_json_str = AppConfig.GOOGLE_DRIVE_TOKEN_JSON
    if not token_json_str:
        print("GOOGLE_DRIVE_TOKEN_JSON is not configured in .env")
        return
        
    try:
        creds_info = json.loads(token_json_str)
        creds = Credentials.from_authorized_user_info(creds_info, scopes=scopes)
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing token...")
            creds.refresh(Request())
            
        print("Authenticated. Accessing sheets API...")
        # Let's try Sheets API
        sheets_service = build("sheets", "v4", credentials=creds)
        spreadsheet_id = "19Gtw2QutX6xChSDanqd79edD3WFYVqooeRiHsK8pGdI"
        
        # Get sheet metadata to verify connection
        meta = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        print("Spreadsheet Title:", meta.get("properties", {}).get("title"))
        sheets = meta.get("sheets", [])
        print("Available sheets (tabs):")
        for s in sheets:
            props = s.get("properties", {})
            print(f"- Title: {props.get('title')}, ID: {props.get('sheetId')}")
            
    except Exception as e:
        print("Failed to access Sheets API:", str(e))
        
        # Let's try Drive API export
        try:
            print("\nTrying Drive API export as CSV...")
            drive_service = build("drive", "v3", credentials=creds)
            # Export the spreadsheet
            export_media = drive_service.files().export(
                fileId="19Gtw2QutX6xChSDanqd79edD3WFYVqooeRiHsK8pGdI",
                mimeType="text/csv"
            ).execute()
            
            # Save locally to inspect
            csv_path = "scratch/exported_sheet.csv"
            os.makedirs("scratch", exist_ok=True)
            with open(csv_path, "wb") as f:
                f.write(export_media)
            print(f"CSV saved to {csv_path}")
            
            # Print first 20 rows using python's csv module to see the structure
            import csv
            with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows = list(reader)
                print(f"Total rows: {len(rows)}")
                print("First 20 rows:")
                for idx, row in enumerate(rows[:30]):
                    print(f"Row {idx+1}: {row}")
                    
        except Exception as ex:
            print("Failed to access Drive API export:", str(ex))

if __name__ == "__main__":
    test_sheet_access()
