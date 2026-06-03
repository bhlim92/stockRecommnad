import csv

def inspect():
    csv_path = "scratch/exported_sheet.csv"
    print("Reading CSV directly using csv.reader...")
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    print(f"Total rows parsed by csv.reader: {len(rows)}")
    
    # Print the headers (first row)
    if rows:
        print("Header row fields count:", len(rows[0]))
        print("Header fields:", rows[0])
        
    print("\nRows with quantity (index 1) > 0:")
    # We inspect rows 2 to 115 in 1-based index (meaning index 1 to 114)
    end_idx = min(115, len(rows))
    for i in range(1, end_idx):
        row = rows[i]
        if len(row) <= 3:
            print(f"Row {i+1} too short: {row}")
            continue
            
        qty_str = row[1].strip()
        ticker = row[2].strip()
        name = row[3].strip()
        
        try:
            qty = float(qty_str.replace(",", ""))
        except ValueError:
            qty = 0.0
            
        if qty > 0:
            print(f"Row {i+1} (1-based index in sheet): Ticker: {ticker}, Name: {repr(name)}, Qty: {qty_str}, Row length: {len(row)}")
            print(f"  Raw fields: {row[:10]} ... {row[17:24] if len(row) > 24 else row[17:]}")

if __name__ == "__main__":
    inspect()
