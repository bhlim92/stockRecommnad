import os
import json
import sys
from app.gspread_fetcher import fetch_portfolio_holdings

def dump():
    print("Fetching portfolio holdings...")
    try:
        holdings = fetch_portfolio_holdings()
        print(f"Fetched {len(holdings)} holdings.")
        
        # Write to JSON file with UTF-8 encoding
        output_file = "scratch/holdings_debug.json"
        os.makedirs("scratch", exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(holdings, f, ensure_ascii=False, indent=2)
        print(f"Dumped holdings to {output_file}")
        
        # Safe print (using repr) to avoid console encoding crashes
        for idx, item in enumerate(holdings):
            print(f"[{idx+1}] Ticker: {item['ticker']}, Name: {repr(item['name'])}, Qty: {item['quantity']}, Current Price: {item['current_price']}, Profit: {item['profit']}, ROI: {item['roi']}, Weight: {item['weight']}")
            
    except Exception as e:
        print("Error fetching or dumping:", str(e))

if __name__ == "__main__":
    dump()
