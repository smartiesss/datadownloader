"""
Debug ticker data - Check what fields are actually in the ticker channel
"""
import asyncio
import json
import websockets
from datetime import datetime

async def test_ticker():
    print("=" * 80)
    print("DEBUGGING TICKER CHANNEL - LOOKING FOR GREEKS")
    print("=" * 80)
    print()

    url = 'wss://www.deribit.com/ws/api/v2'

    async with websockets.connect(url) as ws:
        # Subscribe to ETH option ticker
        subscription = {
            "jsonrpc": "2.0",
            "method": "public/subscribe",
            "params": {
                "channels": ["ticker.ETH-29NOV24-3700-C.100ms"]
            },
            "id": 1
        }

        await ws.send(json.dumps(subscription))
        response = await ws.recv()
        print(f"Subscription: {json.loads(response)}")
        print()

        print("Waiting for ticker messages...")
        print()

        # Get 5 ticker messages
        for i in range(5):
            message = await ws.recv()
            data = json.loads(message)

            if 'params' in data:
                tick_data = data['params'].get('data', {})

                print(f"Message {i+1}:")
                print("-" * 80)
                print(f"Instrument: {tick_data.get('instrument_name')}")
                print(f"Timestamp: {datetime.fromtimestamp(tick_data['timestamp'] / 1000)}")
                print(f"Best bid: {tick_data.get('best_bid_price')}")
                print(f"Best ask: {tick_data.get('best_ask_price')}")
                print(f"Mark price: {tick_data.get('mark_price')}")
                print()

                # Check for Greeks
                print("GREEKS CHECK:")
                greeks = tick_data.get('greeks', {})
                if greeks:
                    print(f"  greeks dictionary: {greeks}")
                    print(f"    delta: {greeks.get('delta')}")
                    print(f"    gamma: {greeks.get('gamma')}")
                    print(f"    theta: {greeks.get('theta')}")
                    print(f"    vega: {greeks.get('vega')}")
                    print(f"    rho: {greeks.get('rho')}")
                else:
                    print("  ❌ NO 'greeks' field in ticker data!")

                print()
                print("IV CHECK:")
                print(f"  mark_iv: {tick_data.get('mark_iv')}")
                print(f"  bid_iv: {tick_data.get('bid_iv')}")
                print(f"  ask_iv: {tick_data.get('ask_iv')}")
                print()

                print("OTHER FIELDS:")
                print(f"  open_interest: {tick_data.get('open_interest')}")
                print(f"  last_price: {tick_data.get('last_price')}")
                print()

                # Print all available keys
                print("ALL AVAILABLE KEYS:")
                print(f"  {sorted(tick_data.keys())}")
                print()
                print("=" * 80)
                print()

if __name__ == "__main__":
    asyncio.run(test_ticker())
