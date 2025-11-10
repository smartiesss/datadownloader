"""
Collector Control API

Provides HTTP endpoints for dynamic subscription management.
Lifecycle manager can send subscribe/unsubscribe commands to collectors.

Endpoints:
- POST /api/subscribe - Subscribe to new instruments
- POST /api/unsubscribe - Unsubscribe from expired instruments
- GET /api/status - Get collector status and subscribed instruments
- GET /health - Health check

Usage:
    Run this alongside the WebSocket collector to enable HTTP control.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Set, Optional
from aiohttp import web
import aiohttp

logger = logging.getLogger(__name__)


class CollectorControlAPI:
    """
    HTTP API for controlling WebSocket collector subscriptions.
    """

    def __init__(
        self,
        collector,
        host: str = '0.0.0.0',
        port: int = 8000
    ):
        """
        Initialize control API.

        Args:
            collector: WebSocketTickCollector instance to control
            host: Host to bind to (default: 0.0.0.0)
            port: Port to bind to (default: 8000)
        """
        self.collector = collector
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None

        # Setup routes
        self.app.router.add_post('/api/subscribe', self.handle_subscribe)
        self.app.router.add_post('/api/unsubscribe', self.handle_unsubscribe)
        self.app.router.add_get('/api/status', self.handle_status)
        self.app.router.add_get('/health', self.handle_health)

        logger.info(f"CollectorControlAPI initialized on {host}:{port}")

    async def start(self):
        """Start the HTTP server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            site = web.TCPSite(self.runner, self.host, self.port)
            await site.start()

            logger.info(f"✅ Control API running on http://{self.host}:{self.port}")

        except Exception as e:
            logger.error(f"Failed to start control API: {e}")
            raise

    async def stop(self):
        """Stop the HTTP server."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Control API stopped")

    async def handle_subscribe(self, request):
        """
        Handle POST /api/subscribe

        Request body:
        {
            "instruments": ["BTC-10NOV25-100000-C", "BTC-10NOV25-100000-P"]
        }

        Response:
        {
            "success": true,
            "subscribed": ["BTC-10NOV25-100000-C", "BTC-10NOV25-100000-P"],
            "already_subscribed": [],
            "failed": []
        }
        """
        try:
            data = await request.json()
            instruments = data.get('instruments', [])

            if not instruments:
                return web.json_response({
                    'success': False,
                    'error': 'No instruments provided'
                }, status=400)

            # Track results
            subscribed = []
            already_subscribed = []
            failed = []

            for instrument in instruments:
                # Check if already subscribed
                if instrument in self.collector.instruments:
                    already_subscribed.append(instrument)
                    continue

                # Add to instruments list
                self.collector.instruments.append(instrument)

                # Subscribe to WebSocket channels if connected
                if self.collector.ws:
                    try:
                        await self._subscribe_instrument(instrument)
                        subscribed.append(instrument)
                        logger.info(f"✅ Subscribed to {instrument}")
                    except Exception as e:
                        failed.append({'instrument': instrument, 'error': str(e)})
                        logger.error(f"Failed to subscribe to {instrument}: {e}")
                else:
                    # WebSocket not connected - will subscribe on next reconnect
                    subscribed.append(instrument)
                    logger.info(f"✅ Queued subscription for {instrument} (WebSocket not connected)")

            response = {
                'success': len(failed) == 0,
                'subscribed': subscribed,
                'already_subscribed': already_subscribed,
                'failed': failed,
                'total_instruments': len(self.collector.instruments)
            }

            return web.json_response(response, status=200)

        except Exception as e:
            logger.error(f"Error in handle_subscribe: {e}", exc_info=True)
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)

    async def handle_unsubscribe(self, request):
        """
        Handle POST /api/unsubscribe

        Request body:
        {
            "instruments": ["BTC-10NOV25-100000-C", "BTC-10NOV25-100000-P"]
        }

        Response:
        {
            "success": true,
            "unsubscribed": ["BTC-10NOV25-100000-C", "BTC-10NOV25-100000-P"],
            "not_found": [],
            "failed": []
        }
        """
        try:
            data = await request.json()
            instruments = data.get('instruments', [])

            if not instruments:
                return web.json_response({
                    'success': False,
                    'error': 'No instruments provided'
                }, status=400)

            # Track results
            unsubscribed = []
            not_found = []
            failed = []

            for instrument in instruments:
                # Check if subscribed
                if instrument not in self.collector.instruments:
                    not_found.append(instrument)
                    continue

                # Remove from instruments list
                self.collector.instruments.remove(instrument)

                # Unsubscribe from WebSocket channels if connected
                if self.collector.ws:
                    try:
                        await self._unsubscribe_instrument(instrument)
                        unsubscribed.append(instrument)
                        logger.info(f"✅ Unsubscribed from {instrument}")
                    except Exception as e:
                        failed.append({'instrument': instrument, 'error': str(e)})
                        logger.error(f"Failed to unsubscribe from {instrument}: {e}")
                else:
                    # WebSocket not connected - already removed from list
                    unsubscribed.append(instrument)
                    logger.info(f"✅ Queued unsubscription for {instrument} (WebSocket not connected)")

            response = {
                'success': len(failed) == 0,
                'unsubscribed': unsubscribed,
                'not_found': not_found,
                'failed': failed,
                'total_instruments': len(self.collector.instruments)
            }

            return web.json_response(response, status=200)

        except Exception as e:
            logger.error(f"Error in handle_unsubscribe: {e}", exc_info=True)
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)

    async def handle_status(self, request):
        """
        Handle GET /api/status

        Response:
        {
            "currency": "BTC",
            "connection_id": 0,
            "instruments_count": 250,
            "instruments": ["BTC-10NOV25-100000-C", ...],
            "websocket_connected": true,
            "last_tick_time": "2025-11-11T10:30:00Z",
            "stats": {
                "ticks_processed": 12345,
                "quotes_received": 10000,
                "trades_received": 50
            }
        }
        """
        try:
            last_tick_str = self.collector.last_tick_time.isoformat() if self.collector.last_tick_time else None

            response = {
                'currency': self.collector.currency,
                'instruments_count': len(self.collector.instruments),
                'instruments': sorted(self.collector.instruments),
                'websocket_connected': self.collector.ws is not None,
                'last_tick_time': last_tick_str,
                'stats': self.collector.stats,
                'running': self.collector.running
            }

            return web.json_response(response, status=200)

        except Exception as e:
            logger.error(f"Error in handle_status: {e}", exc_info=True)
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)

    async def handle_health(self, request):
        """
        Handle GET /health

        Response:
        {
            "status": "healthy",
            "timestamp": "2025-11-11T10:30:00Z"
        }
        """
        return web.json_response({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }, status=200)

    async def _subscribe_instrument(self, instrument: str):
        """
        Subscribe to WebSocket channels for a single instrument.

        Args:
            instrument: Instrument name (e.g., 'BTC-10NOV25-100000-C')
        """
        if not self.collector.ws:
            raise Exception("WebSocket not connected")

        channels = [
            f"ticker.{instrument}.100ms",
            f"trades.{instrument}.100ms"
        ]

        subscription_msg = {
            "jsonrpc": "2.0",
            "method": "public/subscribe",
            "params": {
                "channels": channels
            },
            "id": int(datetime.utcnow().timestamp() * 1000)  # Unique ID
        }

        await self.collector.ws.send(json.dumps(subscription_msg))

        # Wait for confirmation (with timeout)
        try:
            response = await asyncio.wait_for(
                self.collector.ws.recv(),
                timeout=5.0
            )
            response_data = json.loads(response)

            if 'error' in response_data:
                raise Exception(f"Subscription error: {response_data['error']}")

            # Update subscribed channels
            if 'result' in response_data:
                new_channels = response_data['result']
                self.collector.subscribed_channels.update(new_channels)

        except asyncio.TimeoutError:
            raise Exception("Subscription timeout - no response from WebSocket")

    async def _unsubscribe_instrument(self, instrument: str):
        """
        Unsubscribe from WebSocket channels for a single instrument.

        Args:
            instrument: Instrument name (e.g., 'BTC-10NOV25-100000-C')
        """
        if not self.collector.ws:
            raise Exception("WebSocket not connected")

        channels = [
            f"ticker.{instrument}.100ms",
            f"trades.{instrument}.100ms"
        ]

        unsubscription_msg = {
            "jsonrpc": "2.0",
            "method": "public/unsubscribe",
            "params": {
                "channels": channels
            },
            "id": int(datetime.utcnow().timestamp() * 1000)  # Unique ID
        }

        await self.collector.ws.send(json.dumps(unsubscription_msg))

        # Wait for confirmation (with timeout)
        try:
            response = await asyncio.wait_for(
                self.collector.ws.recv(),
                timeout=5.0
            )
            response_data = json.loads(response)

            if 'error' in response_data:
                raise Exception(f"Unsubscription error: {response_data['error']}")

            # Update subscribed channels
            if 'result' in response_data:
                removed_channels = response_data['result']
                for channel in removed_channels:
                    self.collector.subscribed_channels.discard(channel)

        except asyncio.TimeoutError:
            raise Exception("Unsubscription timeout - no response from WebSocket")
