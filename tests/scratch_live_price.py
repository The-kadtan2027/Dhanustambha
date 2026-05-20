import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingestion.fetcher import fetch_live_prices, _scrape_google_finance

def test_live_fetch():
    symbols = ["RELIANCE", "TCS", "INFY"]
    print(f"Testing live fetch for {symbols}...")
    
    # Test Tier 1/2/3 combined
    # results = fetch_live_prices(symbols)
    # print("\nCombined Results:")
    # print(json.dumps(results, indent=2))
    
    # Test Scraper specifically with debug
    print("\nTesting Google Scraper directly for RELIANCE...")
    url = "https://www.google.com/finance/quote/RELIANCE:NSE"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    import requests
    import re
    resp = requests.get(url, headers=headers)
    print(f"Status: {resp.status_code}")
    
    # Search for anything looking like a price near INR or the symbol
    indices = [m.start() for m in re.finditer(r"INR", resp.text)]
    for idx in indices[:5]:
        print(f"\nContext around INR: ...{resp.text[idx-50:idx+150]}...")
    
    # Search for the class identified by the browser subagent
    indices = [m.start() for m in re.finditer(r"YMlKec", resp.text)]
    for idx in indices[:3]:
        print(f"\nContext around YMlKec: ...{resp.text[idx-50:idx+150]}...")

    # Search for the rupee symbol or price-like numbers
    match = re.search(r'₹([\d,]+\.\d{2})', resp.text)
    print(f"\nRupee match: {match}")
    if match:
        print(f"Value: {match.group(1)}")

if __name__ == "__main__":
    test_live_fetch()

if __name__ == "__main__":
    test_live_fetch()
