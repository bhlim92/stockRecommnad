import os
import requests
import hmac
import hashlib
import time
import base64
from dotenv import load_dotenv
load_dotenv()

AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "antigravity-quant-secret-2026-key")
AUTHORIZED_EMAIL = "bumhyun.lim@gmail.com"

def generate_session_token(email: str) -> str:
    expiry = int(time.time()) + 30 * 24 * 60 * 60
    payload = f"{email}:{expiry}"
    signature = hmac.new(AUTH_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    token = f"{payload}:{signature}"
    return base64.b64encode(token.encode()).decode()

def validate_types():
    token = generate_session_token(AUTHORIZED_EMAIL)
    cookies = {"auth_token": token}
    
    url = "https://stock-recommnad.vercel.app/api/portfolio/gspread"
    resp = requests.get(url, cookies=cookies, timeout=20)
    
    if resp.status_code != 200:
        print(f"Error: API returned status code {resp.status_code}")
        return
        
    data = resp.json()
    print(f"Loaded {len(data)} items. Validating fields...")
    
    required_fields = [
        ("ticker", str),
        ("name", str),
        ("quantity", (int, float)),
        ("current_price", (int, float)),
        ("purchase_price", (int, float)),
        ("total_purchase", (int, float)),
        ("total_evaluation", (int, float)),
        ("profit", (int, float)),
        ("roi", str),
        ("weight", str)
    ]
    
    for idx, item in enumerate(data):
        print(f"\nItem {idx+1} ({item.get('ticker')}):")
        for field, expected_type in required_fields:
            val = item.get(field)
            if val is None:
                print(f"  [ERROR] Field '{field}' is None/null!")
            elif not isinstance(val, expected_type):
                print(f"  [ERROR] Field '{field}' has type {type(val)}, expected {expected_type}! Value: {val}")
            else:
                print(f"  [OK] '{field}': {type(val).__name__} ({repr(val)})")

if __name__ == "__main__":
    validate_types()
