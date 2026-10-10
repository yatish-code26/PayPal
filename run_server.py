"""FreightGuard Local Application Server Runner
Starts Uvicorn server on http://127.0.0.1:8000.
"""
import uvicorn
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    print("=" * 70)
    print("  FREIGHTGUARD: Autonomous Freight Financial Control Tower")
    print("  Running on: http://127.0.0.1:8000")
    print("  Mode: LOCAL_DEMO (Deterministic Offline Sandbox Simulator)")
    print("=" * 70)
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, log_level="info")
