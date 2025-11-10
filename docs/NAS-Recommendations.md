# NAS Hardware Recommendations (Non-Synology)

**For**: ETH Options Tick Data Collector (+ BTC, SOL support)
**Budget**: ~$800-$4,000
**Requirements**: 8-bay NAS, any brand hard drives, Docker support
**Date**: 2025-11-09

---

## TL;DR - Top Recommendations

**Best Value**: **QNAP TS-873A** ($950) + 4× 4TB IronWolf ($480) = **$1,430**
**Best Performance**: **QNAP TVS-872XT** ($1,700) + 4× 8TB IronWolf Pro ($1,200) = **$2,900**
**Budget Option**: **TerraMaster F8-423** ($1,200) + 4× 4TB Seagate ($400) = **$1,600**

All support: ✅ Docker ✅ Any brand HDDs ✅ RAID 5/6 ✅ 10GbE (optional)

---

## Comparison Table

| Brand | Model | Bays | CPU | RAM | Price | Docker | 10GbE | RAID | Notes |
|-------|-------|------|-----|-----|-------|--------|-------|------|-------|
| **QNAP** | TS-873A | 8 | AMD Ryzen V1500B (4C/8T) | 8GB (32GB max) | $950 | ✅ | Optional | 0,1,5,6,10 | **Best value** |
| **QNAP** | TVS-872XT | 8 | Intel i5-8400T (6C/6T) | 16GB (64GB max) | $1,700 | ✅ | Built-in | 0,1,5,6,10 | **Best perf** |
| **QNAP** | TS-832PX | 8 | Annapurna Labs AL324 (4C) | 4GB (16GB max) | $650 | ✅ | Built-in | 0,1,5,6 | Budget QNAP |
| **TerraMaster** | F8-423 | 8 | Intel Celeron N5105 (4C) | 4GB (32GB max) | $1,200 | ✅ | Optional | 0,1,5,6 | Good value |
| **TerraMaster** | U8-111 | 8 | Intel Celeron N5105 (4C) | 4GB (16GB max) | $1,000 | ✅ | No | 0,1,5 | Rackmount |
| **Asustor** | AS5304T | 4 | Intel Celeron N5105 (4C) | 4GB (8GB max) | $450 | ✅ | Optional | 0,1,5 | 4-bay option |
| **Asustor** | AS6510T | 10 | Intel Atom C3538 (4C) | 8GB (16GB max) | $1,300 | ✅ | Built-in | 0,1,5,6,10 | 10-bay option |

---

## Detailed Recommendations

### 🥇 #1 Recommendation: QNAP TS-873A

**Price**: $950 (NAS only)
**Why**: Best price/performance, future-proof, excellent Docker support

**Specs**:
- **CPU**: AMD Ryzen V1500B (4-core, 8-thread, 2.2 GHz)
- **RAM**: 8GB DDR4 (expandable to 32GB)
- **Bays**: 8× 3.5" SATA
- **Network**: 2× 2.5GbE (upgradeable to 10GbE with PCIe card)
- **Expansion**: 2× PCIe slots (Gen 3 ×4, Gen 2 ×2)
- **OS**: QTS 5.1 (Linux-based, Docker native)
- **Power**: ~60W idle, ~120W load

**Why This NAS?**:
- ✅ **Any brand HDDs**: WD, Seagate, Toshiba, etc. (NOT locked like Synology)
- ✅ **Excellent Docker support**: QTS Container Station (built-in Docker + docker-compose)
- ✅ **Powerful CPU**: AMD Ryzen (better than Intel Celeron in competitors)
- ✅ **RAM upgrade**: 8GB → 32GB if needed (future-proof)
- ✅ **10GbE ready**: Add PCIe 10GbE card later ($100-200)
- ✅ **RAID 5/6**: Protect against 1-2 drive failures
- ✅ **5-year warranty**: QNAP offers better support than TerraMaster

**Recommended Configuration**:
```
NAS: QNAP TS-873A ($950)
Drives: 4× WD Red Plus 4TB ($120 each = $480)
RAID: RAID 5 (usable capacity: 12TB)
Total: $1,430

Data capacity: 12TB (good for 150+ years of tick data)
Protection: 1 drive can fail without data loss
```

**Alternative Drive Options**:
- **Budget**: 4× Seagate IronWolf 4TB ($100 each = $400)
- **Performance**: 4× WD Red Pro 4TB ($140 each = $560)
- **Capacity**: 4× Seagate IronWolf 8TB ($180 each = $720) → 24TB usable

---

### 🥈 #2 Recommendation: QNAP TVS-872XT

**Price**: $1,700 (NAS only)
**Why**: Best performance, built-in 10GbE, Intel CPU (better Docker compatibility)

**Specs**:
- **CPU**: Intel Core i5-8400T (6-core, 6-thread, 1.7-3.3 GHz)
- **RAM**: 16GB DDR4 (expandable to 64GB)
- **Bays**: 8× 3.5" SATA
- **Network**: 2× 10GbE + 2× GbE
- **Expansion**: 2× PCIe slots (Gen 3 ×8, Gen 3 ×4)
- **OS**: QTS 5.1
- **Power**: ~80W idle, ~150W load

**Why This NAS?**:
- ✅ **10GbE built-in**: No need for expansion card
- ✅ **Intel CPU**: Better compatibility with Linux/Docker images
- ✅ **More RAM**: 16GB standard (vs 8GB in TS-873A)
- ✅ **Better performance**: Intel i5 > AMD Ryzen V1500B for single-threaded tasks
- ✅ **Thunderbolt 3**: Direct attach storage (DAS) mode for backup

**Recommended Configuration**:
```
NAS: QNAP TVS-872XT ($1,700)
Drives: 4× Seagate IronWolf Pro 8TB ($300 each = $1,200)
RAID: RAID 5 (usable capacity: 24TB)
Total: $2,900

Data capacity: 24TB (good for 300+ years of tick data)
Protection: 1 drive can fail without data loss
10GbE: Connect to 10GbE switch for remote Grafana access
```

**Who should buy this?**:
- You have 10GbE network infrastructure
- You want maximum performance
- Budget allows for premium NAS

---

### 🥉 #3 Recommendation: TerraMaster F8-423

**Price**: $1,200 (NAS only)
**Why**: Good value, clean software, alternative to QNAP

**Specs**:
- **CPU**: Intel Celeron N5105 (4-core, 4-thread, 2.0-2.9 GHz)
- **RAM**: 4GB DDR4 (expandable to 32GB)
- **Bays**: 8× 3.5" SATA
- **Network**: 2× 2.5GbE
- **Expansion**: 1× PCIe slot (for 10GbE card)
- **OS**: TOS 5 (Linux-based, Docker support)
- **Power**: ~50W idle, ~100W load

**Why This NAS?**:
- ✅ **Lower price**: $250 cheaper than QNAP TS-873A
- ✅ **Clean software**: TOS 5 is simpler than QTS (less bloat)
- ✅ **Good Docker support**: Built-in Docker container manager
- ✅ **Lower power**: 50W idle vs 60W (save $20/year on electricity)

**Downsides vs QNAP**:
- ⚠️ Weaker CPU (Celeron N5105 vs Ryzen V1500B)
- ⚠️ Less RAM (4GB vs 8GB standard)
- ⚠️ Smaller community (fewer tutorials/guides)
- ⚠️ Warranty: 2 years vs 5 years (QNAP)

**Recommended Configuration**:
```
NAS: TerraMaster F8-423 ($1,200)
Drives: 4× Seagate IronWolf 4TB ($100 each = $400)
RAID: RAID 5 (usable capacity: 12TB)
Total: $1,600

Best for: Budget-conscious buyers who don't need max performance
```

---

## Hard Drive Recommendations

### Budget: Seagate IronWolf (CMR)

**4TB**: $100-110 each
**8TB**: $180-200 each
**Warranty**: 3 years
**Speed**: 5400 RPM (slower but quieter)
**MTBF**: 1M hours
**Workload**: 180 TB/year

**Good for**: Home NAS, low power, quiet operation

---

### Recommended: WD Red Plus (CMR)

**4TB**: $120-130 each
**8TB**: $200-220 each
**Warranty**: 3 years
**Speed**: 5400 RPM
**MTBF**: 1M hours
**Workload**: 180 TB/year

**Good for**: Balance of price, performance, reliability

---

### Performance: Seagate IronWolf Pro (CMR)

**4TB**: $140-160 each
**8TB**: $280-320 each
**Warranty**: 5 years
**Speed**: 7200 RPM (faster)
**MTBF**: 1.2M hours
**Workload**: 300 TB/year

**Good for**: 24/7 operation, higher reliability requirements

---

### ⚠️ AVOID: SMR Drives

**What is SMR?**
- Shingled Magnetic Recording (slower writes)
- Not suitable for RAID (rebuild times: 3-7 days)
- Examples: WD Red (non-Plus), Seagate Archive

**Use only CMR drives** (Conventional Magnetic Recording)

---

## RAID Configuration Recommendations

### RAID 5 (Recommended)

**Configuration**: 4 drives (3 data + 1 parity)
**Usable capacity**: 75% (e.g., 4× 4TB = 12TB usable)
**Protection**: 1 drive can fail
**Write speed**: Good
**Rebuild time**: 12-24 hours (4TB), 24-48 hours (8TB)

**Best for**: Most users (balance of capacity, protection, performance)

---

### RAID 6 (High Protection)

**Configuration**: 4 drives (2 data + 2 parity)
**Usable capacity**: 50% (e.g., 4× 4TB = 8TB usable)
**Protection**: 2 drives can fail
**Write speed**: Slower than RAID 5
**Rebuild time**: 24-48 hours (4TB), 48-72 hours (8TB)

**Best for**: Maximum protection (worth it for 5-year data farming)

---

### RAID 10 (Maximum Performance)

**Configuration**: 4 drives (2 mirrored pairs)
**Usable capacity**: 50% (e.g., 4× 4TB = 8TB usable)
**Protection**: 1 drive per mirror can fail
**Write speed**: Fastest
**Rebuild time**: 6-12 hours (4TB), 12-24 hours (8TB)

**Best for**: Performance over capacity (not needed for tick data)

---

## Sample Configurations

### Configuration 1: Budget (4-Bay Asustor)

```
NAS: Asustor AS5304T ($450)
Drives: 4× Seagate IronWolf 4TB ($100 × 4 = $400)
RAID: RAID 5
Usable: 12TB
Total: $850

Pros:
- Lowest cost
- Good for ETH-only collection
- 4-bay enough for 15+ years

Cons:
- Only 4 bays (no expansion)
- Lower performance
```

---

### Configuration 2: Sweet Spot (8-Bay QNAP)

```
NAS: QNAP TS-873A ($950)
Drives: 4× WD Red Plus 4TB ($120 × 4 = $480)
RAID: RAID 5
Usable: 12TB
Total: $1,430

Pros:
- 8 bays (add 4 more drives later)
- Excellent performance
- Future-proof

Cons:
- None (best value)
```

---

### Configuration 3: Premium (8-Bay QNAP + 10GbE)

```
NAS: QNAP TVS-872XT ($1,700)
Drives: 4× Seagate IronWolf Pro 8TB ($300 × 4 = $1,200)
RAID: RAID 6
Usable: 16TB
Total: $2,900

Pros:
- Maximum performance
- Built-in 10GbE
- 2-drive failure protection
- Intel CPU (best Docker)

Cons:
- Higher cost
```

---

### Configuration 4: Max Capacity (8-Bay + 8 Drives)

```
NAS: QNAP TS-873A ($950)
Drives: 8× Seagate IronWolf 8TB ($180 × 8 = $1,440)
RAID: RAID 6
Usable: 48TB
Total: $2,390

Pros:
- Massive capacity (600+ years of tick data)
- 2-drive failure protection
- All bays populated

Cons:
- High upfront drive cost
- Longer RAID rebuild time
```

---

## Why NOT Synology?

**Problems with Synology**:

1. ❌ **HDD Compatibility List**: Synology requires "approved" drives or shows warnings
2. ❌ **Expensive HDDs**: Synology-branded drives cost 30-50% more
3. ❌ **RAM Lock**: Some models lock RAM slots (can't upgrade)
4. ❌ **Higher Price**: Same specs cost 20-30% more than QNAP/TerraMaster

**Example**:
- Synology DS1821+: $900 (8-bay, Atom C3538, 4GB RAM)
- QNAP TS-873A: $950 (8-bay, Ryzen V1500B, 8GB RAM)
- **QNAP has better CPU + 2× RAM for same price**

---

## Other Options (Not Recommended)

### Unraid (DIY NAS)

**Pros**: Maximum flexibility, any hardware
**Cons**: Licensing cost ($60-130), requires building PC, more complex

**Verdict**: ⚠️ Good for advanced users, but QNAP/TerraMaster is simpler

---

### TrueNAS (DIY NAS)

**Pros**: Free, ZFS filesystem (excellent reliability)
**Cons**: High RAM requirement (16GB+), complex setup, overkill for this use case

**Verdict**: ⚠️ Use only if you're already familiar with FreeNAS/TrueNAS

---

### Buffalo, Netgear, Western Digital NAS

**Verdict**: ❌ Avoid
- Weaker CPUs
- Poor Docker support
- Smaller communities
- Higher failure rates

---

## Shopping Checklist

Before buying, verify:

- ✅ Docker/Container support (check official specs)
- ✅ HDD compatibility (any brand accepted)
- ✅ RAM upgradeable (check max capacity)
- ✅ RAID 5/6 support
- ✅ 2.5GbE or 10GbE (optional but nice)
- ✅ Warranty length (3+ years preferred)
- ✅ Active community (check subreddit/forums)

---

## Final Recommendation

**For most users**: **QNAP TS-873A + 4× WD Red Plus 4TB = $1,430**

**Why?**:
- ✅ Best value for money
- ✅ 8 bays (future expansion)
- ✅ Excellent Docker support
- ✅ Any brand HDDs
- ✅ 12TB usable (more than enough)
- ✅ Room to add BTC, SOL later (just add more drives)

**Where to buy?**:
- Amazon: Usually cheapest
- B&H Photo: Good for US buyers
- Newegg: Sometimes has sales
- Direct from QNAP: Best warranty support

---

## Setup After Purchase

1. **Unbox and install drives**
   - Use RAID 5 (3 data + 1 parity)
   - Initialize filesystem (ext4 or Btrfs)

2. **Update firmware**
   - QTS: System → Firmware Update
   - Always use latest version for Docker compatibility

3. **Enable Docker**
   - App Center → Install "Container Station"
   - Enable SSH access

4. **Deploy collector**
   ```bash
   # SSH into NAS
   ssh admin@nas-ip

   # Clone repo
   git clone https://github.com/youruser/datadownloader.git
   cd datadownloader

   # Configure
   cp .env.example .env
   nano .env  # Set passwords

   # Start
   docker-compose up -d
   ```

5. **Access Grafana**
   - Open: http://nas-ip:3000
   - Login: admin / (your password)

---

## Questions?

**Need help choosing?** Answer these:

1. **Budget**: $800, $1,500, $2,500, or $4,000?
2. **Capacity**: How many years of data? (5 years = 12TB usable)
3. **Performance**: Need 10GbE? (usually no)
4. **Future expansion**: Want to add BTC/SOL later? (get 8-bay)

**Recommendation logic**:
- Budget <$1,000 → **Asustor AS5304T** (4-bay)
- Budget $1,000-$1,500 → **QNAP TS-873A** (8-bay)
- Budget $1,500-$2,500 → **TerraMaster F8-423** (8-bay) or **QNAP TS-873A + more drives**
- Budget $2,500-$4,000 → **QNAP TVS-872XT** (8-bay, 10GbE, best performance)

---

**Last Updated**: 2025-11-09
**Author**: Project Manager
