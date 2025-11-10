#!/usr/bin/env python3
"""
Download BTC historical options data from CryptoDataDownload
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.cryptodatadownload_historical_downloader import CryptoDataDownloadDownloader

def main():
    print("=" * 80)
    print("STARTING BTC OPTIONS HISTORICAL DOWNLOAD")
    print("=" * 80)

    downloader = CryptoDataDownloadDownloader()
    downloader.run_download(currency='BTC')

    print("\n" + "=" * 80)
    print("BTC DOWNLOAD COMPLETE!")
    print("=" * 80)

if __name__ == "__main__":
    main()
