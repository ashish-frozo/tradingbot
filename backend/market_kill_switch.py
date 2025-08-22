#!/usr/bin/env python3
"""
Market Kill Switch - Controls data fetching based on market hours
Automatically stops API calls outside market hours (9:15 AM - 3:30 PM IST)
Provides manual override functionality
"""

import os
from datetime import datetime, time
import pytz
from typing import Dict, Any, Optional

class MarketKillSwitch:
    """
    Kill switch to control data fetching based on:
    1. Market hours (9:15 AM - 3:30 PM IST)
    2. Manual override
    3. Emergency stop
    """
    
    def __init__(self):
        self.manual_override = False  # Manual kill switch
        self.emergency_stop = False   # Emergency stop (highest priority)
        
        # Market hours in IST
        self.market_open_time = time(9, 15)   # 9:15 AM
        self.market_close_time = time(15, 30) # 3:30 PM
        self.ist_timezone = pytz.timezone('Asia/Kolkata')
        
        # Kill switch state file (for persistence across restarts)
        self.state_file = os.path.join(os.path.dirname(__file__), "kill_switch_state.txt")
        
        # Load previous state
        self._load_state()
    
    def _load_state(self):
        """Load kill switch state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = f.read().strip().lower()
                    if state == 'manual_off':
                        self.manual_override = True
                    elif state == 'emergency_stop':
                        self.emergency_stop = True
                    print(f"🔄 Loaded kill switch state: {state}")
        except Exception as e:
            print(f"⚠️ Could not load kill switch state: {e}")
    
    def _save_state(self):
        """Save kill switch state to file"""
        try:
            state = "normal"
            if self.emergency_stop:
                state = "emergency_stop"
            elif self.manual_override:
                state = "manual_off"
            
            with open(self.state_file, 'w') as f:
                f.write(state)
            print(f"💾 Saved kill switch state: {state}")
        except Exception as e:
            print(f"⚠️ Could not save kill switch state: {e}")
    
    def get_ist_time(self) -> datetime:
        """Get current time in IST"""
        return datetime.now(self.ist_timezone)
    
    def is_market_hours(self) -> bool:
        """Check if current time is within market hours (9:15 AM - 3:30 PM IST)"""
        current_time = self.get_ist_time().time()
        
        # Check if current time is between market open and close
        return self.market_open_time <= current_time <= self.market_close_time
    
    def is_weekday(self) -> bool:
        """Check if today is a weekday (Monday = 0, Sunday = 6)"""
        current_date = self.get_ist_time()
        return current_date.weekday() < 5  # Monday to Friday
    
    def should_allow_data_fetching(self) -> Dict[str, Any]:
        """
        Main function to determine if data fetching should be allowed
        Returns dict with decision and reason
        """
        current_ist = self.get_ist_time()
        
        # Priority 1: Emergency stop (highest priority)
        if self.emergency_stop:
            return {
                'allowed': False,
                'reason': 'emergency_stop',
                'message': '🚨 EMERGENCY STOP ACTIVATED - All data fetching disabled',
                'current_time_ist': current_ist.strftime('%Y-%m-%d %H:%M:%S IST')
            }
        
        # Priority 2: Manual override
        if self.manual_override:
            return {
                'allowed': False,
                'reason': 'manual_override',
                'message': '🔴 Manual kill switch activated - Data fetching disabled',
                'current_time_ist': current_ist.strftime('%Y-%m-%d %H:%M:%S IST')
            }
        
        # Priority 3: Check if it's a weekday
        if not self.is_weekday():
            return {
                'allowed': False,
                'reason': 'weekend',
                'message': f'📅 Weekend detected - Market closed (Current: {current_ist.strftime("%A")})',
                'current_time_ist': current_ist.strftime('%Y-%m-%d %H:%M:%S IST')
            }
        
        # Priority 4: Check market hours
        if not self.is_market_hours():
            current_time_str = current_ist.strftime('%H:%M:%S')
            return {
                'allowed': False,
                'reason': 'outside_market_hours',
                'message': f'🕐 Outside market hours - Current: {current_time_str} IST (Market: 09:15-15:30)',
                'current_time_ist': current_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
                'market_status': 'closed'
            }
        
        # All checks passed - allow data fetching
        current_time_str = current_ist.strftime('%H:%M:%S')
        return {
            'allowed': True,
            'reason': 'market_hours',
            'message': f'✅ Market hours active - Data fetching allowed (Current: {current_time_str} IST)',
            'current_time_ist': current_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
            'market_status': 'open'
        }
    
    def activate_manual_kill_switch(self) -> str:
        """Manually activate kill switch"""
        self.manual_override = True
        self._save_state()
        return "🔴 Manual kill switch ACTIVATED - All data fetching stopped"
    
    def deactivate_manual_kill_switch(self) -> str:
        """Manually deactivate kill switch"""
        self.manual_override = False
        self._save_state()
        return "🟢 Manual kill switch DEACTIVATED - Data fetching restored (subject to market hours)"
    
    def activate_emergency_stop(self) -> str:
        """Activate emergency stop (highest priority)"""
        self.emergency_stop = True
        self._save_state()
        return "🚨 EMERGENCY STOP ACTIVATED - All data fetching immediately stopped"
    
    def deactivate_emergency_stop(self) -> str:
        """Deactivate emergency stop"""
        self.emergency_stop = False
        self._save_state()
        return "🟢 Emergency stop DEACTIVATED - Normal kill switch rules apply"
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive kill switch status"""
        decision = self.should_allow_data_fetching()
        current_ist = self.get_ist_time()
        
        return {
            'data_fetching_allowed': decision['allowed'],
            'reason': decision['reason'],
            'message': decision['message'],
            'current_time_ist': current_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
            'market_hours': f"{self.market_open_time.strftime('%H:%M')} - {self.market_close_time.strftime('%H:%M')} IST",
            'is_market_hours': self.is_market_hours(),
            'is_weekday': self.is_weekday(),
            'manual_override': self.manual_override,
            'emergency_stop': self.emergency_stop,
            'market_status': decision.get('market_status', 'unknown')
        }


# Global kill switch instance
_kill_switch = MarketKillSwitch()

def should_allow_data_fetching() -> Dict[str, Any]:
    """
    Main function to check if data fetching should be allowed
    Use this in your API endpoints before making Dhan API calls
    """
    return _kill_switch.should_allow_data_fetching()

def get_kill_switch_status() -> Dict[str, Any]:
    """Get kill switch status"""
    return _kill_switch.get_status()

def activate_manual_kill_switch() -> str:
    """Activate manual kill switch"""
    return _kill_switch.activate_manual_kill_switch()

def deactivate_manual_kill_switch() -> str:
    """Deactivate manual kill switch"""
    return _kill_switch.deactivate_manual_kill_switch()

def activate_emergency_stop() -> str:
    """Activate emergency stop"""
    return _kill_switch.activate_emergency_stop()

def deactivate_emergency_stop() -> str:
    """Deactivate emergency stop"""
    return _kill_switch.deactivate_emergency_stop()


if __name__ == "__main__":
    # Test the kill switch
    print("🧪 Testing Market Kill Switch...")
    
    status = get_kill_switch_status()
    print(f"\n📊 Current Status:")
    print(f"Data Fetching Allowed: {status['data_fetching_allowed']}")
    print(f"Reason: {status['reason']}")
    print(f"Message: {status['message']}")
    print(f"Current Time: {status['current_time_ist']}")
    print(f"Market Hours: {status['market_hours']}")
    print(f"Is Market Hours: {status['is_market_hours']}")
    print(f"Is Weekday: {status['is_weekday']}")
    
    # Test manual controls
    print(f"\n🔄 Testing Manual Controls:")
    print(activate_manual_kill_switch())
    
    status2 = should_allow_data_fetching()
    print(f"After manual kill: {status2['allowed']} - {status2['message']}")
    
    print(deactivate_manual_kill_switch())
    
    status3 = should_allow_data_fetching()
    print(f"After deactivation: {status3['allowed']} - {status3['message']}") 