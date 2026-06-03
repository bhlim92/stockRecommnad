import requests

def test_js():
    url = "https://stock-recommnad.vercel.app/app.js?v=2.2"
    print(f"Fetching {url}...")
    resp = requests.get(url, timeout=10)
    print("Status code:", resp.status_code)
    
    js_content = resp.text
    print("Length of JS file:", len(js_content))
    
    if "loadGspreadPortfolio" in js_content:
        print("SUCCESS: loadGspreadPortfolio is present in the live JS file!")
        # Find where it is defined
        idx = js_content.find("loadGspreadPortfolio")
        print("Context around it:")
        print(js_content[max(0, idx-100):min(len(js_content), idx+300)])
    else:
        print("ERROR: loadGspreadPortfolio is NOT present in the live JS file!")

if __name__ == "__main__":
    test_js()
