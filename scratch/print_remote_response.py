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

def test_remote_raw():
    token = generate_session_token(AUTHORIZED_EMAIL)
    cookies = {"auth_token": token}
    
    url = "https://stock-recommnad.vercel.app/api/portfolio/gspread"
    resp = requests.get(url, cookies=cookies, timeout=20)
    
    raw_content = resp.content
    print("Raw bytes of the response (first 300 bytes):")
    print(raw_content[:300])
    
    try:
        # Try decoding as utf-8
        text_utf8 = raw_content.decode("utf-8")
        print("\nDecoded as UTF-8 (repr):")
        print(repr(text_utf8[:300]))
    except Exception as e:
        print("UTF-8 decoding failed:", str(e))

if __name__ == "__main__":
    test_remote_raw()
