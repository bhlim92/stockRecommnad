import os
import json
import csv
import requests
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.config import AppConfig
from app.utils.logger import setup_logger

logger = setup_logger("gspread_fetcher", "logs/app.log")

def get_google_credentials():
    """
    Retrieves and refreshes Google credentials using user token or service account.
    """
    scopes = ["https://www.googleapis.com/auth/drive"]
    token_json_str = AppConfig.GOOGLE_DRIVE_TOKEN_JSON
    
    # 1. Try OAuth2 user credentials (token.json string)
    if token_json_str:
        try:
            creds_info = json.loads(token_json_str)
            creds = Credentials.from_authorized_user_info(creds_info, scopes=scopes)
            if creds and creds.expired and creds.refresh_token:
                logger.info("User OAuth2 Token expired. Refreshing token...")
                creds.refresh(Request())
            return creds
        except Exception as e:
            logger.error(f"Failed to load/refresh User OAuth2 credentials: {str(e)}")
            if not AppConfig.GOOGLE_APPLICATION_CREDENTIALS:
                raise e

    # 2. Try service account credentials
    cred_path = AppConfig.GOOGLE_APPLICATION_CREDENTIALS
    if cred_path and os.path.exists(cred_path):
        try:
            creds = service_account.Credentials.from_service_account_file(
                cred_path, scopes=scopes
            )
            return creds
        except Exception as e:
            logger.error(f"Failed to load Service Account credentials: {str(e)}")
            raise e

    raise RuntimeError("No Google credentials configured (neither GOOGLE_DRIVE_TOKEN_JSON nor GOOGLE_APPLICATION_CREDENTIALS).")

def fetch_portfolio_holdings():
    """
    Fetches the portfolio stock list from Google Spreadsheet,
    filters row 2 to 115 for holdings > 0, and returns parsed data.
    """
    spreadsheet_id = AppConfig.PORTFOLIO_SPREADSHEET_ID
    gid = AppConfig.PORTFOLIO_SPREADSHEET_GID
    
    if not spreadsheet_id or not gid:
        logger.warning("Portfolio Spreadsheet ID or GID is not configured.")
        return []
        
    try:
        creds = get_google_credentials()
        # Force refresh to make sure token is valid for requests
        if hasattr(creds, "valid") and not creds.valid:
            creds.refresh(Request())
            
        access_token = creds.token
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
        
        logger.info(f"Fetching spreadsheet from Google Drive export URL (GID: {gid})...")
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers, timeout=15)
        
        if resp.status_code != 200:
            logger.error(f"Failed to export spreadsheet. HTTP Status: {resp.status_code}, Response: {resp.text[:200]}")
            raise RuntimeError(f"Failed to fetch spreadsheet. Status code: {resp.status_code}")
            
        resp.encoding = "utf-8"
        csv_content = resp.text
        
        import io
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        
        if not rows:
            logger.warning("Spreadsheet CSV content is empty.")
            return []
            
        holdings = []
        # Parse rows 2 to 115 (1-based index 2 to 115 corresponds to list index 1 to 114)
        # Note: rows index 0 is the header (Row 1).
        end_idx = min(115, len(rows))
        for r_idx in range(1, end_idx):
            row = rows[r_idx]
            if len(row) <= 3:
                continue
                
            qty_str = row[1].strip()
            ticker = row[2].strip()
            name = row[3].strip()
            
            if not qty_str or not ticker:
                continue
                
            # Filter holdings > 0
            try:
                qty = float(qty_str.replace(",", ""))
            except ValueError:
                qty = 0.0
                
            if qty <= 0:
                continue
                
            # Extract additional fields
            def clean_float(val):
                try:
                    return float(val.replace(",", "").replace("$", "").strip())
                except ValueError:
                    return 0.0
            
            current_price = clean_float(row[7]) if len(row) > 7 else 0.0
            purchase_price = clean_float(row[17]) if len(row) > 17 else 0.0
            total_purchase = clean_float(row[18]) if len(row) > 18 else 0.0
            total_evaluation = clean_float(row[19]) if len(row) > 19 else 0.0
            profit = clean_float(row[20]) if len(row) > 20 else 0.0
            roi = row[21].strip() if len(row) > 21 else "0.0%"
            weight = row[23].strip() if len(row) > 23 else "0.0%"
            
            holdings.append({
                "ticker": ticker,
                "name": name,
                "quantity": qty,
                "current_price": current_price,
                "purchase_price": purchase_price,
                "total_purchase": total_purchase,
                "total_evaluation": total_evaluation,
                "profit": profit,
                "roi": roi,
                "weight": weight
            })
            
        logger.info(f"Successfully loaded {len(holdings)} holdings from Google Spreadsheet.")
        return holdings
        
    except Exception as e:
        logger.error(f"Error fetching portfolio holdings: {str(e)}")
        raise e
