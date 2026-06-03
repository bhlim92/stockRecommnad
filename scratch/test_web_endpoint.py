import os
from fastapi.testclient import TestClient
# Override TESTING to True so it bypasses auth middleware in tests
os.environ["TESTING"] = "true"

from app.web_server import app

def test_endpoint():
    client = TestClient(app)
    print("Sending request to /api/portfolio/gspread...")
    resp = client.get("/api/portfolio/gspread")
    print("Status code:", resp.status_code)
    if resp.status_code == 200:
        data = resp.json()
        print(f"Success! Number of holdings: {len(data)}")
        print("First 3 items:")
        for item in data[:3]:
            print(item)
    else:
        print("Error response:", resp.text)

if __name__ == "__main__":
    test_endpoint()
