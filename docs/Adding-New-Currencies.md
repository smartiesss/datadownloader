# How to Add New Currencies

**Quick Guide**: Add BTC, SOL, or any other Deribit-supported currency in 2 minutes

---

## TL;DR - Quick Start

**To add Bitcoin (BTC)**:
```bash
# 1. Edit config file
nano config/currencies.yaml

# 2. Change this line:
#    enabled: false  (under BTC section)
# To:
#    enabled: true

# 3. Restart collector
docker-compose restart collector
```

That's it! BTC options will start collecting immediately.

---

## Step-by-Step Guide

### Option 1: Enable Existing Currency (BTC)

BTC is already configured in `config/currencies.yaml`. Just enable it:

```yaml
# config/currencies.yaml
currencies:
  - symbol: BTC
    enabled: true  # ← Change from false to true
    instrument_types:
      - option
      - future
      - perpetual
    options:
      top_n: 100  # Collect top 100 BTC options
```

**Restart collector**:
```bash
docker-compose restart collector
```

---

### Option 2: Add New Currency (e.g., SOL, MATIC, etc.)

**Step 1**: Check if Deribit supports the currency

Visit: https://www.deribit.com/statistics/BTC/options
Replace `BTC` with your currency symbol (e.g., `SOL`, `MATIC`)

**Step 2**: Add currency to `config/currencies.yaml`

```yaml
currencies:
  # Copy this template for new currency
  - symbol: SOL  # ← Your currency symbol
    enabled: true
    instrument_types:
      - option  # SOL options
      - future  # SOL futures
      - perpetual  # SOL-PERPETUAL
    options:
      top_n: 50  # Number of options to collect (0 = all)
      min_open_interest: 1  # Filter threshold
      min_volume_24h: 1000  # USD volume threshold
    futures:
      include_all: true  # Collect all futures
    perpetual:
      enabled: true  # Collect perpetual
    priority: 4  # Processing priority (lower = higher)
```

**Step 3**: Update database schema (if needed)

If you're collecting a new currency for the first time, you may want to create separate tables:

```sql
-- Option 1: Use same tables (recommended)
-- No changes needed - all currencies share eth_option_quotes and eth_option_trades

-- Option 2: Create currency-specific tables (advanced)
CREATE TABLE IF NOT EXISTS sol_option_quotes (
    -- Same schema as eth_option_quotes
    timestamp TIMESTAMPTZ NOT NULL,
    instrument TEXT NOT NULL,
    best_bid_price NUMERIC(18, 8),
    best_bid_amount NUMERIC(18, 8),
    best_ask_price NUMERIC(18, 8),
    best_ask_amount NUMERIC(18, 8),
    underlying_price NUMERIC(18, 8),
    mark_price NUMERIC(18, 8),
    PRIMARY KEY (timestamp, instrument)
);
```

**Step 4**: Restart collector

```bash
docker-compose restart collector
```

**Step 5**: Verify collection

```bash
# Check logs
docker-compose logs -f collector | grep "SOL"

# Check database
docker exec -it eth-timescaledb psql -U postgres -d crypto_data -c "
  SELECT instrument, COUNT(*) as ticks
  FROM eth_option_quotes
  WHERE instrument LIKE 'SOL-%'
  GROUP BY instrument
  ORDER BY ticks DESC
  LIMIT 10;
"
```

---

## Configuration Options Explained

### `top_n` - How many options to collect

```yaml
options:
  top_n: 50  # Collect top 50 by open interest
  top_n: 0   # Collect ALL options (can be 2,000+ for BTC)
  top_n: 100 # Recommended for BTC
```

**Calculation**:
- ETH: ~830 options → top 50 = 6% coverage (most active)
- BTC: ~2,500 options → top 100 = 4% coverage (most active)
- SOL: ~200 options (estimated) → top 30 = 15% coverage

### `min_open_interest` - Filter low-liquidity options

```yaml
options:
  min_open_interest: 0   # No filtering (collect all)
  min_open_interest: 10  # Skip options with <10 BTC open interest
```

Use this to skip illiquid options that rarely trade.

### `min_volume_24h` - Filter low-volume options

```yaml
options:
  min_volume_24h: 0      # No filtering
  min_volume_24h: 10000  # Skip options with <$10k volume
```

Useful for BTC (many options, low liquidity).

### `priority` - Collection order

```yaml
currencies:
  - symbol: ETH
    priority: 1  # Collect first
  - symbol: BTC
    priority: 2  # Collect second
  - symbol: SOL
    priority: 3  # Collect third
```

Lower number = higher priority. Affects subscription order and reconnect behavior.

---

## Subscription Limits

**Deribit Limits**:
- Max connections: 3
- Max subscriptions per connection: 500
- **Total max**: 3 × 500 = 1,500 subscriptions

**Subscription Calculation**:

Each instrument = 2 channels (quotes + trades)

Example:
```
ETH:
  50 options × 2 = 100
  7 futures × 2 = 14
  1 perpetual × 2 = 2
  Total = 116 subscriptions

BTC:
  100 options × 2 = 200
  7 futures × 2 = 14
  1 perpetual × 2 = 2
  Total = 216 subscriptions

Combined: 116 + 216 = 332 subscriptions (22% of limit)
```

**Safe Limits**:
- 1 currency (ETH/BTC): up to 700 options
- 2 currencies: up to 350 options each
- 3 currencies: up to 230 options each

---

## Data Volume Estimates

### Per Currency (24 hours)

**ETH** (50 options):
- Ticks: 600,000-1,000,000/day
- Size: 40-60 MB/day (uncompressed)
- Size: 12-18 MB/day (compressed 70%)

**BTC** (100 options):
- Ticks: 1,200,000-2,000,000/day
- Size: 80-120 MB/day (uncompressed)
- Size: 24-36 MB/day (compressed 70%)

**SOL** (30 options, estimated):
- Ticks: 360,000-600,000/day
- Size: 24-40 MB/day (uncompressed)
- Size: 7-12 MB/day (compressed 70%)

**Total** (ETH + BTC + SOL):
- Ticks: ~2.2-3.6M/day
- Size: 144-220 MB/day (uncompressed)
- Size: 43-66 MB/day (compressed 70%)
- **5 years**: 78-120 GB (compressed)

---

## NAS Storage Requirements

### Minimum NAS Specs (ETH + BTC + SOL, 5 years)

**Storage**:
- Data: 120 GB (compressed)
- Backups: 50 GB (weekly backups × 4)
- OS + Apps: 30 GB
- **Total**: 200 GB minimum
- **Recommended**: 1-2 TB (for growth + safety margin)

**RAID**: RAID 1 (mirroring) or RAID 5 (striping + parity)
**Drives**: 2× 2TB (RAID 1) or 4× 1TB (RAID 5)

---

## Example Configurations

### Configuration 1: ETH Only (Conservative)

```yaml
currencies:
  - symbol: ETH
    enabled: true
    options:
      top_n: 50
    futures:
      include_all: true
    perpetual:
      enabled: true
```

**Subscriptions**: 116
**Data**: 12-18 MB/day (compressed)
**5-year storage**: 22-33 GB

---

### Configuration 2: ETH + BTC (Recommended)

```yaml
currencies:
  - symbol: ETH
    enabled: true
    options:
      top_n: 50
    priority: 1

  - symbol: BTC
    enabled: true
    options:
      top_n: 100
    priority: 2
```

**Subscriptions**: 332
**Data**: 36-54 MB/day (compressed)
**5-year storage**: 66-99 GB

---

### Configuration 3: All Currencies (Aggressive)

```yaml
currencies:
  - symbol: ETH
    enabled: true
    options:
      top_n: 100  # Increased from 50
    priority: 1

  - symbol: BTC
    enabled: true
    options:
      top_n: 200  # Increased from 100
    priority: 2

  - symbol: SOL
    enabled: true  # Enabled
    options:
      top_n: 50
    priority: 3
```

**Subscriptions**: 716
**Data**: 80-120 MB/day (compressed)
**5-year storage**: 146-219 GB

---

## Troubleshooting

### "Too many subscriptions" error

**Error**:
```
ERROR: Subscription limit exceeded (max 500 per connection)
```

**Fix**:
Reduce `top_n` values or disable a currency:

```yaml
currencies:
  - symbol: ETH
    options:
      top_n: 30  # ← Reduce from 50

  - symbol: BTC
    enabled: false  # ← Disable if needed
```

---

### "Instrument not found" error

**Error**:
```
WARNING: Instrument SOL-29NOV24-150-C not found
```

**Fix**:
Currency not supported by Deribit yet. Check https://www.deribit.com/

---

### Slow collection / high buffer usage

**Error**:
```
WARNING: Quotes buffer 85.3% full (threshold: 80%)
```

**Fix**:
Increase buffer sizes or reduce `top_n`:

```yaml
global:
  buffer_size_quotes: 400000  # ← Increase from 200000
  flush_interval_sec: 2  # ← Decrease from 3 (flush more often)
```

---

## Next Steps

1. ✅ Edit `config/currencies.yaml`
2. ✅ Set `enabled: true` for desired currencies
3. ✅ Restart collector: `docker-compose restart collector`
4. ✅ Monitor logs: `docker-compose logs -f collector`
5. ✅ Verify data: Check database for new instrument ticks

**Need help?** See [DEPLOYMENT.md](../DEPLOYMENT.md) for full deployment guide.
