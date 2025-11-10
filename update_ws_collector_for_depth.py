"""
Script to update ws_tick_collector.py to support full depth WebSocket collection
"""

import re

# Read the current file
with open('/Users/doghead/PycharmProjects/datadownloader/scripts/ws_tick_collector.py', 'r') as f:
    content = f.read()

# 1. Update buffer initialization to include max_depth
content = re.sub(
    r'self\.buffer = TickBuffer\(\s*max_quotes=buffer_size_quotes,\s*max_trades=buffer_size_trades\s*\)',
    '''self.buffer = TickBuffer(
            max_quotes=buffer_size_quotes,
            max_trades=buffer_size_trades,
            max_depth=50000  # Buffer for full depth snapshots
        )''',
    content
)

# 2. Update _handle_quote_tick to extract and save full depth
old_handle_quote = r'''    async def _handle_quote_tick\(self, data: Dict\):
        """
        Handle quote tick from book\.\{instrument\}\.100ms channel\.

        Args:
            data: Quote data from WebSocket
        """
        try:
            # Extract quote data
            quote = \{
                'timestamp': datetime\.fromtimestamp\(data\['timestamp'\] / 1000\),
                'instrument_name': data\['instrument_name'\],
                'best_bid_price': data\.get\('best_bid_price'\),
                'best_bid_amount': data\.get\('best_bid_amount'\),
                'best_ask_price': data\.get\('best_ask_price'\),
                'best_ask_amount': data\.get\('best_ask_amount'\),
                'underlying_price': data\.get\('underlying_price'\),
                'mark_price': data\.get\('mark_price'\)
            \}

            # Add to buffer
            self\.buffer\.add_quote\(quote\)
            self\.stats\['quotes_received'\] \+= 1

        except Exception as e:
            logger\.error\(f"Failed to process quote tick: \{e\}"\)
            self\.stats\['errors'\] \+= 1'''

new_handle_quote = '''    async def _handle_quote_tick(self, data: Dict):
        """
        Handle quote tick from book.{instrument}.100ms channel.

        Args:
            data: Quote data from WebSocket
        """
        try:
            # Extract quote data (best bid/ask for Level 1)
            quote = {
                'timestamp': datetime.fromtimestamp(data['timestamp'] / 1000),
                'instrument_name': data['instrument_name'],
                'best_bid_price': data.get('best_bid_price'),
                'best_bid_amount': data.get('best_bid_amount'),
                'best_ask_price': data.get('best_ask_price'),
                'best_ask_amount': data.get('best_ask_amount'),
                'underlying_price': data.get('underlying_price'),
                'mark_price': data.get('mark_price')
            }

            # Add to buffer
            self.buffer.add_quote(quote)
            self.stats['quotes_received'] += 1

            # Extract full depth data (all levels) if available
            bids = data.get('bids', [])
            asks = data.get('asks', [])

            if bids or asks:
                # Convert Deribit format [[price, amount], ...] to JSONB format
                bids_json = [{"price": float(bid[0]), "amount": float(bid[1])} for bid in bids] if bids else []
                asks_json = [{"price": float(ask[0]), "amount": float(ask[1])} for ask in asks] if asks else []

                depth = {
                    'timestamp': datetime.fromtimestamp(data['timestamp'] / 1000),
                    'instrument': data['instrument_name'],
                    'bids': bids_json,
                    'asks': asks_json,
                    'mark_price': data.get('mark_price'),
                    'underlying_price': data.get('underlying_price'),
                    'open_interest': data.get('open_interest'),
                    'volume_24h': data.get('stats', {}).get('volume') if 'stats' in data else None
                }

                # Add depth snapshot to buffer
                self.buffer.add_depth(depth)
                self.stats['depth_received'] = self.stats.get('depth_received', 0) + 1

        except Exception as e:
            logger.error(f"Failed to process quote tick: {e}")
            self.stats['errors'] += 1'''

content = re.sub(old_handle_quote, new_handle_quote, content, flags=re.DOTALL)

# 3. Update _flush_buffers to flush depth snapshots
old_flush = r'''    async def _flush_buffers\(self\):
        """Flush buffers to database\."""
        try:
            # Get and clear buffers \(atomic operation\)
            quotes, trades = self\.buffer\.get_and_clear\(\)

            # Write to database
            if quotes:
                await self\.writer\.write_quotes\(quotes\)

            if trades:
                await self\.writer\.write_trades\(trades\)

        except Exception as e:
            logger\.error\(f"Failed to flush buffers: \{e\}", exc_info=True\)
            self\.stats\['errors'\] \+= 1'''

new_flush = '''    async def _flush_buffers(self):
        """Flush buffers to database."""
        try:
            # Get and clear buffers (atomic operation)
            quotes, trades, depth = self.buffer.get_and_clear()

            # Write to database
            if quotes:
                await self.writer.write_quotes(quotes)

            if trades:
                await self.writer.write_trades(trades)

            if depth:
                await self.writer.write_depth_snapshots(depth)

        except Exception as e:
            logger.error(f"Failed to flush buffers: {e}", exc_info=True)
            self.stats['errors'] += 1'''

content = re.sub(old_flush, new_flush, content, flags=re.DOTALL)

# 4. Update stats initialization to include depth_received
content = re.sub(
    r"'connection_attempts': 0,\s*'reconnections': 0,\s*'ticks_processed': 0,\s*'quotes_received': 0,\s*'trades_received': 0,\s*'errors': 0",
    "'connection_attempts': 0,\n            'reconnections': 0,\n            'ticks_processed': 0,\n            'quotes_received': 0,\n            'trades_received': 0,\n            'depth_received': 0,\n            'errors': 0",
    content
)

# 5. Update stats logger to include depth stats
old_stats_log = r'''logger\.info\(\s*f"STATS \| Ticks: \{self\.stats\['ticks_processed'\]\} "\s*f"\| Quotes: \{self\.stats\['quotes_received'\]\} "\s*f"\| Trades: \{self\.stats\['trades_received'\]\} "\s*f"\| Errors: \{self\.stats\['errors'\]\} "\s*f"\| Buffer: Q=\{buffer_stats\['quotes'\]\['utilization_pct'\]:.1f\}% "\s*f"T=\{buffer_stats\['trades'\]\['utilization_pct'\]:.1f\}% "\s*f"\| DB Writes: Q=\{writer_stats\['quotes_written'\]\} "\s*f"T=\{writer_stats\['trades_written'\]\}"\s*\)'''

new_stats_log = '''logger.info(
                    f"STATS | Ticks: {self.stats['ticks_processed']} "
                    f"| Quotes: {self.stats['quotes_received']} "
                    f"| Trades: {self.stats['trades_received']} "
                    f"| Depth: {self.stats.get('depth_received', 0)} "
                    f"| Errors: {self.stats['errors']} "
                    f"| Buffer: Q={buffer_stats['quotes']['utilization_pct']:.1f}% "
                    f"T={buffer_stats['trades']['utilization_pct']:.1f}% "
                    f"D={buffer_stats['depth']['utilization_pct']:.1f}% "
                    f"| DB Writes: Q={writer_stats['quotes_written']} "
                    f"T={writer_stats['trades_written']}"
                )'''

content = re.sub(old_stats_log, new_stats_log, content, flags=re.DOTALL)

# Write the updated file
with open('/Users/doghead/PycharmProjects/datadownloader/scripts/ws_tick_collector.py', 'w') as f:
    f.write(content)

print("✅ ws_tick_collector.py updated successfully")
print("   - Added max_depth to buffer initialization")
print("   - Updated _handle_quote_tick to extract full depth")
print("   - Updated _flush_buffers to flush depth snapshots")
print("   - Added depth_received to stats")
print("   - Updated stats logger to include depth metrics")
