import csv

def print_uni():
    csv_path = "scratch/exported_sheet.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
        # print row 1 with repr
        print("Header Row repr:")
        print(repr(rows[0]))
        
        print("\nAll rows with quantity > 0:")
        for idx, row in enumerate(rows[1:116]): # Rows 2 to 115
            # Columns: 
            # col 1 is quantity
            # col 2 is Ticker
            # col 3 is Name
            qty_str = row[1].strip() if len(row) > 1 else "0"
            ticker = row[2].strip() if len(row) > 2 else ""
            name = row[3].strip() if len(row) > 3 else ""
            
            # Let's check if qty > 0
            try:
                # remove comma if present
                qty_clean = qty_str.replace(",", "")
                qty = float(qty_clean)
            except ValueError:
                qty = 0.0
                
            if qty > 0:
                print(f"Row {idx+2}: Ticker={ticker}, Name={name}, Quantity={qty}, Raw Qty='{qty_str}'")

if __name__ == "__main__":
    print_uni()
