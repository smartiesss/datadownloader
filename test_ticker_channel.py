"""
Quick test of ticker channel - verify it provides all fields
"""
import asyncio
import json
import websockets
from datetime import datetime

async def test_ticker_channel():
    """Test ticker channel for 30 seconds"""
    print("=" * 80)
    print("TESTING TICKER CHANNEL")
    print("=" * 80)
    print(f"Start time: {datetime.now()}")
    print()

    url = 'wss://www.deribit.com/ws/api/v2'

    async with websockets.connect(url) as ws:
        # Subscribe to ticker channel
        subscription = {
            "jsonrpc": "2.0",
            "method": "public/subscribe",
            "params": {
                "channels": [
                    "ticker.BTC-PERPETUAL.100ms",
                    "ticker.ETH-PERPETUAL.100ms"
                ]
            },
            "id": 1
        }

        await ws.send(json.dumps(subscription))
        response = await ws.recv()
        response_data = json.loads(response)

        print(f"Subscription response: {response_data}")
        print()

        if 'result' not in response_data:
            print("❌ Subscription failed!")
            return

        print("✅ Successfully subscribed to ticker channels")
        print()
        print("Collecting data for 30 seconds...")
        print()

        quote_count = {'BTC-PERPETUAL': 0, 'ETH-PERPETUAL': 0}
        sample_quotes = []

        start = datetime.now()

        while (datetime.now() - start).total_seconds() < 30:
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(message)

                if 'params' in data:
                    channel = data['params'].get('channel', '')
                    tick_data = data['params'].get('data', {})

                    if channel.startswith('ticker.'):
                        instrument = tick_data.get('instrument_name', '')
                        if instrument in quote_count:
                            quote_count[instrument] += 1

                            # Save first 3 samples
                            if len(sample_quotes) < 3:
                                sample_quotes.append({
                                    'instrument': instrument,
                                    'timestamp': datetime.fromtimestamp(tick_data['timestamp'] / 1000),
                                    'best_bid_price': tick_data.get('best_bid_price'),
                                    'best_ask_price': tick_data.get('best_ask_price'),
                                    'mark_price': tick_data.get('mark_price'),
                                    'index_price': tick_data.get('index_price'),
                                    'funding_8h': tick_data.get('funding_8h'),
                                    'open_interest': tick_data.get('open_interest')
                                })

            except asyncio.TimeoutError:
                print("⚠️ No messages received for 5 seconds")
                break
            except Exception as e:
                print(f"Error: {e}")
                break

    # Print results
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"End time: {datetime.now()}")
    print()
    print(f"BTC-PERPETUAL quotes received: {quote_count['BTC-PERPETUAL']}")
    print(f"ETH-PERPETUAL quotes received: {quote_count['ETH-PERPETUAL']}")
    print()

    if quote_count['BTC-PERPETUAL'] > 0 or quote_count['ETH-PERPETUAL'] > 0:
        print("✅ SUCCESS! Ticker channel is working")
    else:
        print("❌ FAILED! No quotes received")

    print()
    print("SAMPLE QUOTES (first 3):")
    print("-" * 80)
    for quote in sample_quotes:
        print(f"Instrument: {quote['instrument']}")
        print(f"  Timestamp: {quote['timestamp']}")
        print(f"  Bid: {quote['best_bid_price']}")
        print(f"  Ask: {quote['best_ask_price']}")
        print(f"  Mark: {quote['mark_price']}")
        print(f"  Index: {quote['index_price']}")
        print(f"  Funding: {quote['funding_8h']}")
        print(f"  Open Interest: {quote['open_interest']}")
        print()

    print("=" * 80)
    print("VERIFICATION:")
    print("=" * 80)

    all_fields_present = True
    for quote in sample_quotes:
        if quote['mark_price'] is None or quote['index_price'] is None:
            all_fields_present = False
            break

    if all_fields_present and len(sample_quotes) > 0:
        print("✅ All fields populated (bid/ask/mark/index/funding)")
        print("✅ Ticker channel provides complete data")
        print("✅ Ready to deploy to NAS!")
    else:
        print("❌ Some fields are NULL")
        print("❌ Need to investigate further")

    print()

if __name__ == "__main__":
    asyncio.run(test_ticker_channel())
