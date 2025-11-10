"""
Test script to see what data Deribit WebSocket actually sends.
This will help debug the NULL data issue.
"""

import asyncio
import json
import websockets
from datetime import datetime


async def test_websocket_data():
    """Connect to Deribit WebSocket and print raw messages."""

    ws_url = "wss://www.deribit.com/ws/api/v2"

    print(f"Connecting to {ws_url}...")

    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
        print("✅ Connected!")

        # Subscribe to a single instrument to see data format
        test_instrument = "ETH-10NOV25-3200-C"

        subscription_msg = {
            "jsonrpc": "2.0",
            "method": "public/subscribe",
            "params": {
                "channels": [f"book.{test_instrument}.100ms"]
            },
            "id": 1
        }

        print(f"\n📡 Subscribing to: book.{test_instrument}.100ms")
        await ws.send(json.dumps(subscription_msg))

        # Receive subscription confirmation
        response = await ws.recv()
        print(f"\n✅ Subscription response:")
        print(json.dumps(json.loads(response), indent=2))

        # Receive and print first 5 data messages
        print(f"\n📊 Waiting for data messages (showing first 5)...")
        count = 0

        async for message in ws:
            data = json.loads(message)

            # Only show data messages (not heartbeats)
            if 'params' in data:
                count += 1
                print(f"\n--- Message {count} ---")
                print(f"Time: {datetime.now()}")
                print(f"Channel: {data['params'].get('channel', 'unknown')}")
                print(f"Data keys: {list(data['params'].get('data', {}).keys())}")
                print(f"Full data:")
                print(json.dumps(data['params']['data'], indent=2))

                if count >= 5:
                    print("\n✅ Test complete!")
                    break


if __name__ == "__main__":
    asyncio.run(test_websocket_data())
