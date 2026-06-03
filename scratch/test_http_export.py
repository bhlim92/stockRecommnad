import os
import json
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from app.config import AppConfig

def test_http_export():
    scopes = ["https://www.googleapis.com/auth/drive"]
    token_json_str = AppConfig.GOOGLE_DRIVE_TOKEN_JSON
    creds_info = json.loads(token_json_str)
    creds = Credentials.from_authorized_user_info(creds_info, scopes=scopes)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        
    access_token = creds.token
    print("Access token retrieved:", access_token[:15] + "...")
    
    spreadsheet_id = "19Gtw2QutX6xChSDanqd79edD3WFYVqooeRiHsK8pGdI"
    gid = "1126172231"
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
    headers = {"Authorization": f"Bearer {access_token}"}
    print(f"Fetching {url} using Authorization Bearer token...")
    resp = requests.get(url, headers=headers, timeout=10)
    print("Status code:", resp.status_code)
    if resp.status_code == 200:
        print("Success! CSV row count:", len(resp.text.splitlines()))
        print("First line:", resp.text.splitlines()[0])
    else:
        print("Error response:", resp.text[:200])

if __name__ == "__main__":
    test_http_export()
