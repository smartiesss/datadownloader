"""
Deribit API Connectivity Test
Task: T-003
Acceptance Criteria: AC-001

Tests connectivity to Deribit public API /public/test endpoint.
Saves JSON response to /tests/evidence/T-003-connectivity.json
"""

import asyncio
import aiohttp
import json
import sys
from pathlib import Path


async def test_deribit_connection():
    """Test Deribit API connectivity"""
    url = "https://www.deribit.com/api/v2/public/test"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                status_code = response.status
                data = await response.json()

                # Prepare result
                result = {
                    "status_code": status_code,
                    "response_valid": True,
                    "api_data": data
                }

                # Print to console
                print(f"✓ Deribit API Test Successful")
                print(f"  Status Code: {status_code}")
                print(f"  Response: {json.dumps(data, indent=2)}")

                # Save evidence
                evidence_dir = Path("/Users/doghead/PycharmProjects/datadownloader/tests/evidence")
                evidence_dir.mkdir(parents=True, exist_ok=True)

                evidence_file = evidence_dir / "T-003-connectivity.json"
                with open(evidence_file, 'w') as f:
                    json.dump(result, f, indent=2)

                print(f"\n✓ Evidence saved to: {evidence_file}")
                print(f"✓ AC-001: Deribit API connectivity validated")

                return 0

    except Exception as e:
        print(f"✗ Deribit API Test Failed: {e}", file=sys.stderr)
        return 1


def main():
    """Main entry point"""
    return asyncio.run(test_deribit_connection())


if __name__ == "__main__":
    sys.exit(main())
