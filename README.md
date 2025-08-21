# Nifty Options Trading Platform

A comprehensive real-time trading platform for Indian stock market (Nifty) options trading with advanced market sentiment analysis.
pip install -r requirements.txt
```

## Getting Started

### 1. Get Your API Credentials

To use the Dhan API, you'll need:
- **Client ID**: Your Dhan client ID
- **Access Token**: Your API access token

You can obtain these from your Dhan account dashboard.

### 2. Configure Credentials

Edit the `dhan_trading_example.py` file and replace the placeholder values:

```python
CLIENT_ID = "your_client_id"  # Replace with your actual client ID
ACCESS_TOKEN = "your_access_token"  # Replace with your actual access token
```

### 3. Run the Example

```bash
python dhan_trading_example.py
```

## Features

The Dhan-Tradehull package provides:

- **Market Data**: Real-time quotes, historical data
- **Order Management**: Place, modify, cancel orders
- **Portfolio**: Get positions, holdings, fund limits
- **Trade Book**: View completed trades
- **Options Trading**: Advanced options analysis with Black-Scholes pricing

## API Functions Available

- `get_fund_limits()` - Get available funds
- `get_positions()` - Get current positions
- `get_holdings()` - Get current holdings
- `place_order()` - Place buy/sell orders
- `get_order_list()` - Get order history
- `get_trade_book()` - Get trade history
- `get_quote()` - Get real-time quotes

## Important Notes

⚠️ **Security**: Never commit your actual API credentials to version control. Consider using environment variables or a separate config file.

⚠️ **Testing**: Always test with small quantities first when placing orders.

⚠️ **Rate Limits**: Be aware of API rate limits to avoid being blocked.

## Documentation

For detailed API documentation, visit:
- [Dhan-Tradehull PyPI Page](https://pypi.org/project/Dhan-Tradehull/)
- [Dhan API Documentation](https://dhanhq.co/docs/v2/)

## Support

For issues with the Dhan-Tradehull package, please check:
- PyPI package issues
- Dhan developer documentation
- Community forums 