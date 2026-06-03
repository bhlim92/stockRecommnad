import os
import requests
import hmac
import hashlib
import time
import base64

# Load secret key from local .env
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

def test_remote():
    token = generate_session_token(AUTHORIZED_EMAIL)
    cookies = {"auth_token": token}
    
    url = "https://stock-recommnad.vercel.app/api/portfolio/gspread"
    print(f"Sending GET request to {url} with auth cookie...")
    
    try:
        resp = requests.get(url, cookies=cookies, timeout=20)
        print("Status code:", resp.status_code)
        print("Response headers:", resp.headers)
        print("Response text (first 500 chars):")
        print(resp.text[:500])
    except Exception as e:
        print("Request failed:", str(e))

if __name__ == "__main__":
    test_remote()
