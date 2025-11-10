# Database Access Guide

**How to access tick data from external programs**

---

## Overview

Your TimescaleDB database is accessible via standard PostgreSQL connections. This guide shows how to connect from:

1. Python programs
2. Jupyter notebooks
3. Docker containers
4. Other languages (Node.js, Go, etc.)
5. BI tools (Tableau, PowerBI, etc.)

---

## Connection Information

### Local PostgreSQL (Current Setup)

```
Host: localhost
Port: 5432
Database: crypto_data
User: postgres
Password: (from your .env file)
```

### Docker Deployment (When deployed to NAS)

```
Host: nas-ip (e.g., 192.168.1.100)
Port: 5432
Database: crypto_data
User: postgres
Password: (from your .env file)
```

**Important**: If connecting from inside Docker, use `timescaledb` as host instead of `localhost`.

---

## Method 1: Python (Recommended)

### Using asyncpg (Async, Fastest)

```python
import asyncpg
import asyncio

async def query_data():
    conn = await asyncpg.connect(
        host='localhost',  # or NAS IP
        port=5432,
        database='crypto_data',
        user='postgres',
        password='your_password'
    )
    
    rows = await conn.fetch("""
        SELECT timestamp, instrument, best_bid_price, best_ask_price
        FROM eth_option_quotes
        WHERE timestamp >= NOW() - INTERVAL '1 hour'
        ORDER BY timestamp DESC
        LIMIT 100
    """)
    
    for row in rows:
        print(row)
    
    await conn.close()

asyncio.run(query_data())
```

### Using psycopg2 (Sync, Simpler)

```python
import psycopg2
import pandas as pd

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='crypto_data',
    user='postgres',
    password='your_password'
)

# Query to Pandas DataFrame
df = pd.read_sql("""
    SELECT * FROM eth_option_quotes
    WHERE timestamp >= NOW() - INTERVAL '1 hour'
""", conn)

print(df.head())
conn.close()
```

---

## Method 2: Docker Container Access

If your analysis program runs in Docker, add it to the same network:

### Option A: Add to existing docker-compose.yml

```yaml
services:
  my_analysis_app:
    image: python:3.12-slim
    container_name: my-analysis
    environment:
      POSTGRES_HOST: timescaledb  # Use service name, not localhost!
      POSTGRES_PORT: 5432
      POSTGRES_DB: crypto_data
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    networks:
      - crypto_net
```

### Option B: Connect standalone container to existing network

```bash
# Run your container on the same network
docker run -it --network datadownloader_crypto_net \
  -e POSTGRES_HOST=timescaledb \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_DB=crypto_data \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=your_password \
  python:3.12-slim bash
```

---

## Method 3: Jupyter Notebook

See: `examples/access_from_jupyter.ipynb`

```python
import psycopg2
import pandas as pd

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='crypto_data',
    user='postgres',
    password='your_password'
)

df = pd.read_sql("SELECT * FROM eth_option_quotes LIMIT 1000", conn)
df.head()
```

---

## Method 4: Other Languages

### Node.js

```javascript
const { Client } = require('pg');

const client = new Client({
  host: 'localhost',
  port: 5432,
  database: 'crypto_data',
  user: 'postgres',
  password: 'your_password'
});

await client.connect();

const res = await client.query(`
  SELECT * FROM eth_option_quotes
  WHERE timestamp >= NOW() - INTERVAL '1 hour'
  LIMIT 100
`);

console.log(res.rows);
await client.end();
```

### Go

```go
package main

import (
    "database/sql"
    "fmt"
    _ "github.com/lib/pq"
)

func main() {
    connStr := "host=localhost port=5432 user=postgres password=your_password dbname=crypto_data sslmode=disable"
    db, err := sql.Open("postgres", connStr)
    if err != nil {
        panic(err)
    }
    defer db.Close()

    rows, err := db.Query("SELECT timestamp, instrument FROM eth_option_quotes LIMIT 10")
    if err != nil {
        panic(err)
    }
    defer rows.Close()

    for rows.Next() {
        var timestamp string
        var instrument string
        rows.Scan(&timestamp, &instrument)
        fmt.Println(timestamp, instrument)
    }
}
```

---

## Method 5: BI Tools (Tableau, PowerBI, Metabase)

### Tableau

1. Data → New Data Source
2. Select "PostgreSQL"
3. Server: `localhost` (or NAS IP)
4. Port: `5432`
5. Database: `crypto_data`
6. Authentication: Username/Password
7. Select tables: `eth_option_quotes`, `eth_option_trades`

### PowerBI

1. Get Data → Database → PostgreSQL
2. Server: `localhost:5432`
3. Database: `crypto_data`
4. DirectQuery or Import

### Metabase (Open Source, Recommended)

Add to docker-compose.yml:

```yaml
services:
  metabase:
    image: metabase/metabase:latest
    container_name: eth-metabase
    ports:
      - "3001:3000"
    environment:
      MB_DB_TYPE: postgres
      MB_DB_DBNAME: metabase
      MB_DB_PORT: 5432
      MB_DB_USER: postgres
      MB_DB_PASS: ${POSTGRES_PASSWORD}
      MB_DB_HOST: timescaledb
    networks:
      - crypto_net
```

Access: http://localhost:3001

---

## Common Queries

### Get latest tick for each instrument

```sql
SELECT DISTINCT ON (instrument)
    instrument,
    timestamp,
    best_bid_price,
    best_ask_price,
    underlying_price
FROM eth_option_quotes
ORDER BY instrument, timestamp DESC;
```

### Calculate tick rate (ticks per minute)

```sql
SELECT 
    time_bucket('1 minute', timestamp) as minute,
    COUNT(*) as ticks_per_minute
FROM eth_option_quotes
WHERE timestamp >= NOW() - INTERVAL '1 hour'
GROUP BY minute
ORDER BY minute DESC;
```

### Get option chain for specific expiry

```sql
SELECT DISTINCT
    instrument,
    best_bid_price,
    best_ask_price,
    mark_price
FROM eth_option_quotes
WHERE instrument LIKE 'ETH-29NOV24%'
AND timestamp >= NOW() - INTERVAL '5 minutes'
ORDER BY instrument;
```

### Calculate average spread by instrument

```sql
SELECT 
    instrument,
    COUNT(*) as tick_count,
    AVG(best_ask_price - best_bid_price) as avg_spread,
    MIN(best_ask_price - best_bid_price) as min_spread,
    MAX(best_ask_price - best_bid_price) as max_spread
FROM eth_option_quotes
WHERE timestamp >= NOW() - INTERVAL '1 day'
GROUP BY instrument
ORDER BY tick_count DESC
LIMIT 50;
```

---

## Security Considerations

### 1. Change Default Password

```bash
# In .env file
POSTGRES_PASSWORD=your_very_secure_password_here
```

### 2. Firewall Rules (NAS Deployment)

Only allow connections from trusted IPs:

```bash
# QNAP firewall
# Control Panel → Security → Firewall
# Add rule: Allow port 5432 from specific IP only
```

### 3. Read-Only User (Recommended)

Create a read-only user for analysis programs:

```sql
-- Connect as postgres user
CREATE USER readonly_user WITH PASSWORD 'readonly_password';
GRANT CONNECT ON DATABASE crypto_data TO readonly_user;
GRANT USAGE ON SCHEMA public TO readonly_user;
GRANT SELECT ON eth_option_quotes, eth_option_trades TO readonly_user;

-- Now use this user for external connections
```

### 4. SSL/TLS (Production)

For production, enable SSL:

```yaml
# docker-compose.yml
timescaledb:
  command:
    - "postgres"
    - "-c"
    - "ssl=on"
    - "-c"
    - "ssl_cert_file=/var/lib/postgresql/server.crt"
    - "-c"
    - "ssl_key_file=/var/lib/postgresql/server.key"
```

---

## Troubleshooting

### "Connection refused"

- Check if TimescaleDB is running: `docker-compose ps timescaledb`
- Verify port 5432 is exposed: `docker-compose port timescaledb 5432`
- Check firewall: `telnet localhost 5432`

### "Authentication failed"

- Verify password in .env file
- Check username (default: `postgres`)
- Ensure database exists: `docker exec -it eth-timescaledb psql -U postgres -l`

### "Database does not exist"

- Database name is `crypto_data` (not `postgres`)
- Verify: `docker exec -it eth-timescaledb psql -U postgres -l`

### Slow queries

- Add indexes: `CREATE INDEX ON eth_option_quotes (instrument, timestamp DESC);`
- Use TimescaleDB compression (automatically enabled for data >30 days old)
- Use time_bucket for aggregations

---

## Examples

See the `examples/` directory:
- `access_database_python.py` - 5 Python examples
- `access_from_jupyter.ipynb` - Jupyter notebook
- `docker_compose_integration.yml` - Docker integration

---

**Next Steps**:
1. Try the Python example: `python examples/access_database_python.py`
2. Create your own analysis script
3. Build custom dashboards in Grafana/Metabase
4. Export data for backtesting strategies

