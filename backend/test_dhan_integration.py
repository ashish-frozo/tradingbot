"""
Test Dhan API integration for fetching real market data
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add the backend directory to the Python path
sys.path.append('/Users/ashishdhiman/niftytradesetup/niftytradesetup/backend')

from app.services.market_data_fetcher import MarketDataFetcher
from app.services.historical_data_service import historical_service

async def test_dhan_integration():
    """Test Dhan API integration"""
    print("🚀 Testing Dhan API Integration...")
    
    # Initialize market data fetcher
    fetcher = MarketDataFetcher()
    
    # Test 1: Fetch historical Nifty prices
    print("\n📈 Test 1: Fetching Nifty historical prices...")
    try:
        nifty_data = fetcher.fetch_nifty_historical_prices(days=5)
        print(f"✅ Fetched {len(nifty_data)} data points")
        print(f"Date range: {nifty_data['Date'].min()} to {nifty_data['Date'].max()}")
        print(f"Price range: {nifty_data['Close'].min():.2f} to {nifty_data['Close'].max():.2f}")
        
        # Show sample data
        print("\nSample data:")
        print(nifty_data[['Date', 'Time', 'Close', 'Volume']].head())
        
    except Exception as e:
        print(f"❌ Error fetching Nifty data: {e}")
    
    # Test 2: Fetch option chain data
    print("\n⚙️ Test 2: Fetching option chain data...")
    try:
        option_snapshots = fetcher.fetch_option_chain_historical(days=3)
        print(f"✅ Generated {len(option_snapshots)} option chain snapshots")
        
        if option_snapshots:
            sample = option_snapshots[0]
            print(f"Sample snapshot: {sample.date} {sample.timestamp}")
            print(f"Spot: {sample.spot:.2f}, Expiry: {sample.expiry}")
            print(f"Strikes available: {len(sample.strikes)}")
            
            # Show sample strike data
            if sample.strikes:
                strike = sample.strikes[0]
                print(f"Sample strike {strike['strike']}: Call LTP={strike['call']['ltp']}, Put LTP={strike['put']['ltp']}")
        
    except Exception as e:
        print(f"❌ Error fetching option chain: {e}")
    
    # Test 3: Convert to historical signals
    print("\n🔄 Test 3: Converting to historical signals...")
    try:
        if 'option_snapshots' in locals() and option_snapshots:
            signals = fetcher.convert_to_historical_signals(option_snapshots[:10])  # Test with first 10
            print(f"✅ Converted {len(signals)} snapshots to signals")
            
            if signals:
                sample_signal = signals[0]
                print(f"Sample signal: {sample_signal.timestamp}")
                print(f"RR25: {sample_signal.rr25:.4f}, GEX: {sample_signal.gex:.2f}")
                print(f"Max OI Pin: {sample_signal.max_oi_pin:.2f}")
        
    except Exception as e:
        print(f"❌ Error converting signals: {e}")
    
    # Test 4: Store in historical database
    print("\n💾 Test 4: Storing historical signals...")
    try:
        if 'signals' in locals() and signals:
            await historical_service.store_signal_batch(signals[:5])  # Store first 5
            print("✅ Successfully stored signals in database")
            
            # Verify storage
            stats = await historical_service.get_zscore_stats()
            print(f"Database stats: {len(stats)} signal types stored")
        
    except Exception as e:
        print(f"❌ Error storing signals: {e}")
    
    print("\n🎉 Dhan integration test completed!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_dhan_integration())
