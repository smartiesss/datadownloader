"""
Test if Deribit ticker channel provides Greeks for options
"""
import asyncio
import json
import websockets
from datetime import datetime

async def test_option_ticker():
    """Check what fields are in option ticker data"""
    print("=" * 80)
    print("TESTING OPTION TICKER DATA - CHECKING FOR GREEKS")
    print("=" * 80)
    print()

    url = 'wss://www.deribit.com/ws/api/v2'

    async with websockets.connect(url) as ws:
        # Subscribe to an ETH option ticker
        subscription = {
            "jsonrpc": "2.0",
            "method": "public/subscribe",
            "params": {
                "channels": ["ticker.ETH-10NOV25-3200-C.100ms"]
            },
            "id": 1
        }

        await ws.send(json.dumps(subscription))
        response = await ws.recv()
        print(f"Subscription response: {json.loads(response)}")
        print()

        print("Waiting for ticker data...")
        print()

        # Get first ticker message
        message = await ws.recv()
        data = json.loads(message)

        if 'params' in data:
            tick_data = data['params'].get('data', {})

            print("TICKER DATA FIELDS:")
            print("-" * 80)
            for key, value in sorted(tick_data.items()):
                print(f"{key:25} = {value}")
            print()

            # Check for Greeks
            greeks_fields = ['delta', 'gamma', 'theta', 'vega', 'implied_volatility', 'iv']
            found_greeks = [f for f in greeks_fields if f in tick_data]

            print("=" * 80)
            print("GREEKS AVAILABILITY:")
            print("=" * 80)
            if found_greeks:
                print(f"✅ Found Greeks fields: {found_greeks}")
            else:
                print("❌ NO GREEKS in ticker channel!")
                print()
                print("Available fields:")
                print(", ".join(sorted(tick_data.keys())))

if __name__ == "__main__":
    asyncio.run(test_option_ticker())
