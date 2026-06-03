import requests

def inspect():
    url = "https://docs.google.com/spreadsheets/d/19Gtw2QutX6xChSDanqd79edD3WFYVqooeRiHsK8pGdI/export?format=csv&gid=1126172231"
    print(f"Fetching {url}...")
    try:
        resp = requests.get(url, timeout=10)
        print(f"Status code: {resp.status_code}")
        print("Content length:", len(resp.text))
        lines = resp.text.splitlines()
        print("First 15 lines:")
        for i, line in enumerate(lines[:15]):
            print(f"{i+1}: {line}")
    except Exception as e:
        print("Error:", str(e))

if __name__ == "__main__":
    inspect()
