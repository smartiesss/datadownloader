# ETH Options Tick Data Collector

Real-time WebSocket collector for Deribit ETH options tick data, optimized for NAS deployment (QNAP/TerraMaster).

## Features

- ✅ Real-time tick data collection (quotes + trades)
- ✅ Multi-currency support (ETH, BTC, SOL)
- ✅ TimescaleDB time-series database
- ✅ Docker deployment (one-command setup)
- ✅ Auto-reconnect on network failures
- ✅ Grafana visualization
- ✅ NAS-optimized (low CPU/RAM usage)
- ✅ YAML-based configuration (no code changes)

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/youruser/datadownloader.git
cd datadownloader

# 2. Configure environment
cp .env.example .env
nano .env  # Change passwords

# 3. Deploy
docker-compose up -d

# 4. Verify
docker-compose logs -f collector

# 5. Access Grafana
# Open: http://nas-ip:3000 (admin/admin)
```

## Architecture

```
Deribit WebSocket API
         ↓
   ETH Collector (Python)
   - AsyncIO WebSocket
   - Thread-safe buffer
   - Batch inserts
         ↓
   TimescaleDB (PostgreSQL)
   - Time-series optimized
   - 70% compression
         ↓
   Grafana Dashboards
   - Real-time charts
   - Alert system
```

## Storage Requirements

| Configuration | Daily | 1 Year | 5 Years |
|--------------|-------|--------|---------|
| Top 50 ETH options | 18 MB | 6.7 GB | 33 GB |
| Top 100 ETH options | 36 MB | 13.3 GB | 67 GB |
| All ETH options (830) | 303 MB | 110 GB | 552 GB |
| ETH + BTC (100 each) | 54 MB | 20 GB | 133 GB |

## Hardware Requirements

**Minimum** (ETH only, top 50):
- NAS: 4-bay, 4GB RAM
- Storage: 500 GB (1× 1TB drive)
- Network: 1GbE

**Recommended** (ETH + BTC, top 100 each):
- NAS: 8-bay, 8GB RAM (QNAP TS-873A / QU805)
- Storage: 2 TB usable (RAID 5: 4× 1TB drives)
- Network: 2.5GbE

## Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Complete NAS deployment guide
- [Adding-New-Currencies.md](docs/Adding-New-Currencies.md) - How to add BTC/SOL
- [NAS-Recommendations.md](docs/NAS-Recommendations.md) - Hardware buying guide
- [Storage-Estimates.md](docs/Storage-Estimates.md) - Storage calculations

## Project Status

- ✅ T-001: WebSocket collector (COMPLETED)
- ✅ T-002: Multi-currency support (COMPLETED)
- ⏳ T-003: Grafana dashboards (PENDING)
- ⏳ T-004: Automated backups (PENDING)

## License

MIT
