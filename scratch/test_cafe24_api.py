import requests

def test_cafe24():
    urls = [
        "http://bhlim123.cafe24.com/api/status",
        "http://bhlim123.cafe24.com/api/portfolio/gspread",
        "http://bhlim123.cafe24.com/"
    ]
    
    for url in urls:
        print(f"\nFetching {url}...")
        try:
            resp = requests.get(url, timeout=10)
            print("Status code:", resp.status_code)
            print("Headers:", resp.headers)
            print("Content (first 200 chars):")
            print(resp.text[:200])
        except Exception as e:
            print("Failed:", str(e))

if __name__ == "__main__":
    test_cafe24()
