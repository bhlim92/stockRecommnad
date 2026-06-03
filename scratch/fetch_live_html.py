import requests

def test_html():
    url = "https://stock-recommnad.vercel.app/"
    print(f"Fetching {url}...")
    resp = requests.get(url, timeout=10)
    print("Status code:", resp.status_code)
    
    html_content = resp.text
    print("Length of HTML file:", len(html_content))
    
    if "holdings-list" in html_content:
        print("SUCCESS: holdings-list is present in the live HTML file!")
    else:
        print("ERROR: holdings-list is NOT present in the live HTML file!")
        
    if "app.js?v=2.3" in html_content:
        print("SUCCESS: app.js?v=2.3 is referenced in the live HTML file!")
    else:
        print("ERROR: app.js?v=2.3 is NOT referenced in the live HTML file!")
        # Let's see what scripts are referenced
        import re
        scripts = re.findall(r'<script.*?>', html_content)
        print("Scripts in HTML:", scripts)

if __name__ == "__main__":
    test_html()
