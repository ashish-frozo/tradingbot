"""
Market hours utility for Indian stock market timing
"""
from datetime import datetime, time
import pytz

# Indian Standard Time
IST = pytz.timezone('Asia/Kolkata')

def is_market_open():
    """Check if Indian stock market is currently open"""
    now = datetime.now(IST)
    
    # Check if it's a weekday (Monday=0, Sunday=6)
    if now.weekday() > 4:  # Saturday or Sunday
        return False
    
    # Market hours: 9:15 AM to 3:30 PM IST
    market_open = time(9, 15)
    market_close = time(15, 30)
    
    current_time = now.time()
    return market_open <= current_time <= market_close

def is_pre_market():
    """Check if it's pre-market hours (9:00-9:15 AM IST)"""
    now = datetime.now(IST)
    
    if now.weekday() > 4:  # Weekend
        return False
    
    pre_market_start = time(9, 0)
    pre_market_end = time(9, 15)
    
    current_time = now.time()
    return pre_market_start <= current_time < pre_market_end

def is_market_day():
    """Check if today is a market trading day (Monday-Friday)"""
    now = datetime.now(IST)
    return now.weekday() < 5

def get_market_status():
    """Get current market status"""
    if not is_market_day():
        return "CLOSED_WEEKEND"
    
    if is_pre_market():
        return "PRE_MARKET"
    
    if is_market_open():
        return "OPEN"
    
    now = datetime.now(IST)
    if now.time() < time(9, 0):
        return "CLOSED_BEFORE_MARKET"
    else:
        return "CLOSED_AFTER_MARKET"

def should_fetch_data():
    """Determine if data fetching should be active"""
    status = get_market_status()
    return status in ["PRE_MARKET", "OPEN"]

def get_next_market_open():
    """Get the next market opening time"""
    now = datetime.now(IST)
    
    # If it's before 9:15 AM on a weekday, return today's opening
    if now.weekday() < 5 and now.time() < time(9, 15):
        return now.replace(hour=9, minute=15, second=0, microsecond=0)
    
    # Otherwise, find next weekday
    days_ahead = 1
    while True:
        next_day = now.replace(hour=9, minute=15, second=0, microsecond=0)
        next_day = next_day.replace(day=now.day + days_ahead)
        
        if next_day.weekday() < 5:  # Weekday
            return next_day
        
        days_ahead += 1
        if days_ahead > 7:  # Safety check
            break
    
    return None
