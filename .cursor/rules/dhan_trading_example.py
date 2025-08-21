#!/usr/bin/env python3
"""
Dhan-Tradehull API Example
This file demonstrates basic usage of the Dhan-Tradehull trading API.
"""

from dhanhq import dhanhq

# Configuration
CLIENT_ID = "your_client_id"  # Replace with your actual client ID
ACCESS_TOKEN = "your_access_token"  # Replace with your actual access token

def initialize_dhan_client():
    """Initialize the Dhan client with credentials."""
    dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
    return dhan

def get_fund_limits(dhan):
    """Get fund limits for your account."""
    try:
        fund_limits = dhan.get_fund_limits()
        print("Fund Limits:", fund_limits)
        return fund_limits
    except Exception as e:
        print(f"Error getting fund limits: {e}")
        return None

def get_positions(dhan):
    """Get current positions."""
    try:
        positions = dhan.get_positions()
        print("Current Positions:", positions)
        return positions
    except Exception as e:
        print(f"Error getting positions: {e}")
        return None

def get_holdings(dhan):
    """Get current holdings."""
    try:
        holdings = dhan.get_holdings()
        print("Current Holdings:", holdings)
        return holdings
    except Exception as e:
        print(f"Error getting holdings: {e}")
        return None

def place_order(dhan, symbol, quantity, price, order_type="BUY"):
    """
    Place an order (example - modify parameters as needed).
    
    Args:
        dhan: Dhan client instance
        symbol: Trading symbol
        quantity: Order quantity
        price: Order price
        order_type: BUY or SELL
    """
    try:
        # Example order parameters - modify as needed
        order_response = dhan.place_order(
            security_id="1333",  # NSE security ID for reliance
            exchange_segment=dhan.NSE,
            transaction_type=dhan.BUY if order_type == "BUY" else dhan.SELL,
            quantity=quantity,
            order_type=dhan.LIMIT,
            price=price,
            product_type=dhan.INTRA,
            validity=dhan.DAY
        )
        print("Order placed successfully:", order_response)
        return order_response
    except Exception as e:
        print(f"Error placing order: {e}")
        return None

def get_order_list(dhan):
    """Get list of orders."""
    try:
        orders = dhan.get_order_list()
        print("Order List:", orders)
        return orders
    except Exception as e:
        print(f"Error getting orders: {e}")
        return None

def get_trade_book(dhan):
    """Get trade book."""
    try:
        trades = dhan.get_trade_book()
        print("Trade Book:", trades)
        return trades
    except Exception as e:
        print(f"Error getting trade book: {e}")
        return None

def get_quote(dhan, security_id):
    """Get quote for a security."""
    try:
        quote = dhan.get_quote(
            security_id=security_id,
            exchange_segment=dhan.NSE
        )
        print("Quote:", quote)
        return quote
    except Exception as e:
        print(f"Error getting quote: {e}")
        return None

def main():
    """Main function to demonstrate API usage."""
    print("=== Dhan-Tradehull API Example ===")
    
    # Initialize client
    dhan = initialize_dhan_client()
    
    # Get account information
    print("\n1. Getting Fund Limits...")
    get_fund_limits(dhan)
    
    print("\n2. Getting Positions...")
    get_positions(dhan)
    
    print("\n3. Getting Holdings...")
    get_holdings(dhan)
    
    print("\n4. Getting Orders...")
    get_order_list(dhan)
    
    print("\n5. Getting Trade Book...")
    get_trade_book(dhan)
    
    print("\n6. Getting Quote for Reliance...")
    get_quote(dhan, "1333")  # Reliance security ID
    
    # Example of placing an order (commented out for safety)
    # print("\n7. Placing Order (Example)...")
    # place_order(dhan, "RELIANCE", 1, 2500.0, "BUY")

if __name__ == "__main__":
    main() 