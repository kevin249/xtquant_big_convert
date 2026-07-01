# coding: utf-8
"""Client-side private config example for MiniQMT-compatible replacement.

Copy this file to:

    src/bigqmt_signal_trader_client_config.py

Do not commit the real file. It may contain account ids and Redis credentials.
"""

BIGQMT_ACCOUNT_ID = "YOUR_ACCOUNT_ID"
BIGQMT_RPC_TIMEOUT_SECONDS = 6.0

BIGQMT_REDIS_CONFIG = {
    "host": "YOUR_REDIS_HOST",
    "port": 6379,
    "db": 5,
    "username": "",
    "password": "",
}

# Client-side get_full_tick reads Redis snapshots instead of making RPC calls.
# The client renews demand for 10 seconds and waits briefly for the first fill.
BIGQMT_FULL_TICK_CACHE_CONFIG = {
    "enabled": True,
    "demand_ttl_seconds": 10,
    "cache_ttl_seconds": 10,
    "wait_seconds": 3.5,
    "poll_interval_seconds": 0.2,
}
