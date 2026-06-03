import requests

def fetch_js():
    url = "https://stock-recommnad.vercel.app/app.js"
    print(f"Requesting {url}...")
    resp = requests.get(url, timeout=10)
    print("Status code:", resp.status_code)
    print("File size:", len(resp.text))
    if "loadGspreadPortfolio" in resp.text:
        print("Success! loadGspreadPortfolio is in the script!")
    else:
        print("Warning: loadGspreadPortfolio is NOT in the script!")

if __name__ == "__main__":
    fetch_js()
