import requests

def fetch_live():
    url = "https://stock-recommnad.vercel.app/api/portfolio/gspread"
    print(f"Requesting {url}...")
    try:
        resp = requests.get(url, timeout=10)
        print("Status code:", resp.status_code)
        print("Response body:")
        print(resp.text[:500])
    except Exception as e:
        print("Error:", str(e))

if __name__ == "__main__":
    fetch_live()
