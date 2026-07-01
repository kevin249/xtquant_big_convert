# coding: utf-8
"""Local private config example for the QMT python directory.

Copy this file to the QMT python directory as:

    bigqmt_signal_trader_local_config.py

Do not commit the real file. It may contain account ids and Redis credentials.
"""

BIGQMT_ACCOUNT_ID = "YOUR_ACCOUNT_ID"

BIGQMT_REDIS_CONFIG = {
    "host": "127.0.0.1",
    "port": 6379,
    "db": 5,
    "username": "",
    "password": "",
    # Keep order RPC disabled unless you explicitly want remote order/cancel.
    "rpc_allow_order_methods": False,
    # How often the strategy thread drains the RPC queue (via run_time("adjust", ...)).
    # This is the dominant read-RPC latency: a request waits up to one interval before
    # it executes. Lower = lower latency but more load on the strategy thread. Confirm
    # on the live box that run_time honors the value (see the "adjust cadence" log line)
    # before trusting a low value; if it is clamped, latency stays high silently.
    "schedule_adjust_interval": "500nMilliSecond",
    # get_full_tick is served by a demand-driven Redis cache.
    # When a client calls get_full_tick, it renews demand for 10 seconds.
    # Symbol-list demands refresh every full_tick_refresh_interval_seconds; whole-market
    # (SH/SZ/BJ/HK) demands refresh on the slower market interval so a ~50k row snapshot
    # is not pulled every fast tick.
    "full_tick_cache_enabled": True,
    "full_tick_demand_ttl_seconds": 10,
    "full_tick_cache_ttl_seconds": 10,
    "full_tick_refresh_interval_seconds": 0.5,
    "full_tick_market_refresh_interval_seconds": 3,
    # Wall-clock budget for one refresh round; keeps a slow round from stalling the
    # strategy thread (the in-flight demand always completes).
    "full_tick_refresh_max_wall_seconds": 0.3,
    "full_tick_max_requests": 8,
}
