import os
from dhanhq import dhanhq
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Dhan API Configuration
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

# Initialize Dhan API
dhan = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)

print("=== DEBUGGING DHAN API RESPONSES ===")
print(f"Client ID: {DHAN_CLIENT_ID}")
print(f"Token: {DHAN_ACCESS_TOKEN[:20]}...")

print("\n=== FUND LIMITS ===")
try:
    fund_data = dhan.get_fund_limits()
    print(json.dumps(fund_data, indent=2))
except Exception as e:
    print(f"Error: {e}")

print("\n=== POSITIONS ===")
try:
    positions_data = dhan.get_positions()
    print(json.dumps(positions_data, indent=2))
except Exception as e:
    print(f"Error: {e}")

print("\n=== HOLDINGS ===")
try:
    holdings_data = dhan.get_holdings()
    print(json.dumps(holdings_data, indent=2))
except Exception as e:
    print(f"Error: {e}")

print("\n=== ORDER BOOK ===")
try:
    orders_data = dhan.get_order_list()
    print(json.dumps(orders_data, indent=2))
except Exception as e:
    print(f"Error: {e}")
