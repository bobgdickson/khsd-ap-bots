from datetime import datetime
from dateutil import parser
from pathlib import Path

def normalize_date(date_str: str) -> str:
    """
    Convert various date formats into mm/dd/yyyy
    """
    try:
        dt = parser.parse(date_str, dayfirst=False, fuzzy=True)
        return dt.strftime("%m/%d/%Y")
    except Exception:
        return None
    
def generate_runid(vendor_key: str, test_mode: bool = False) -> str:
    ts = datetime.now().strftime("%m-%d-%y-%H-%M")
    prefix = "test-" if test_mode else ""
    return f"{prefix}{vendor_key.capitalize()}-{ts}"

def get_invoices_in_data():
    data_dir = Path("data")
    if not data_dir.exists():
        print("Data directory does not exist. Please create it and add invoice files.")
        return []
    invoices = [str(file) for file in data_dir.glob("*.pdf")]
    if not invoices:
        print("No invoice files found in the 'data' directory.")
    print(f"Found {len(invoices)} invoice files in 'data' directory.")
    return invoices