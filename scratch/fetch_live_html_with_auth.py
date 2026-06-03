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

def test_html_auth():
    token = generate_session_token(AUTHORIZED_EMAIL)
    cookies = {"auth_token": token}
    
    url = "https://stock-recommnad.vercel.app/"
    print(f"Fetching {url} with auth cookie...")
    resp = requests.get(url, cookies=cookies, timeout=10)
    print("Status code:", resp.status_code)
    print("Length of HTML file:", len(resp.text))
    
    html_content = resp.text
    if "holdings-list" in html_content:
        print("SUCCESS: holdings-list is present in the live authenticated HTML!")
    else:
        print("ERROR: holdings-list is NOT present in the live authenticated HTML!")
        
    if "app.js?v=2.3" in html_content:
        print("SUCCESS: app.js?v=2.3 is referenced in the live authenticated HTML!")
    else:
        print("ERROR: app.js?v=2.3 is NOT referenced in the live authenticated HTML!")
        
    # Print the last 20 lines of HTML to verify script tags
    lines = html_content.splitlines()
    print("\nLast 15 lines of HTML:")
    for line in lines[-15:]:
        print(line)

if __name__ == "__main__":
    test_html_auth()
