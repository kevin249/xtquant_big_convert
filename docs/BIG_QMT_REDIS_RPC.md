# 大 QMT Redis Pub/Sub RPC 说明

更新时间：2026-07-01

## 目标

在大 QMT 策略进程内启动一个 Redis Pub/Sub 订阅器，用来远程调用少量白名单方法：

- `ping`
- `get_ticks`
- `get_instrument`
- `get_market_data` / `get_market_data_ex` / `get_local_data`
- `get_stock_list_in_sector` / `get_sector_list` / `get_sector_info`
- `get_divid_factors` / `download_history_data` / `download_history_data2`
- `get_trading_dates` / `get_holidays` / `download_holiday_data`
- `get_ipo_info` / `get_etf_info` / `get_option_list`
- `get_financial_data` / `download_financial_data`
- `call_formula` / `subscribe_formula` / `unsubscribe_formula` / `get_formula_result` / `gen_factor_index`
- `get_positions`
- `get_asset`
- `query_orders`
- `query_trades`
- `sync_positions`

下单类方法 `submit_order`、`cancel_order` 默认关闭，只有显式配置 `rpc_allow_order_methods=True` 后才会开放。

## MiniQMT 兼容方法名

RPC 服务端会把以下 MiniQMT 常用方法名映射到大 QMT 适配器：

| MiniQMT 方法名 | RPC 内部方法 | 说明 |
|---|---|---|
| `query_stock_asset` | `get_asset` | 查询账户资产 |
| `query_stock_positions` | `get_positions` | 查询全部持仓 |
| `query_stock_position` | `query_stock_position` | 查询单只持仓，按 `stock_code` 过滤 |
| `query_stock_orders` | `query_orders` | 查询委托；支持 `cancelable_only` 过滤 |
| `query_stock_trades` | `query_trades` | 查询成交 |
| `get_full_tick` | `get_ticks` | RPC 白名单仍保留；MiniQMT 兼容层默认改为 Redis 快照缓存读取 |
| `get_instrument_detail` / `get_instrumentdetail` | `get_instrument` | 查询合约详情 |
| `order_stock` / `order_stock_async` | `submit_order` | 买卖下单；默认关闭 |
| `cancel_order_stock` / `cancel_order_stock_sysid` | `cancel_order` | 撤单；默认关闭 |

`order_stock` 参数兼容 `stock_code`、`order_type`、`order_volume`、`price_type`、`price`、`strategy_name`、`order_remark`。其中 `order_type=23/STOCK_BUY` 映射为买入，`order_type=24/STOCK_SELL` 映射为卖出。

`price_type` 会透传到大 QMT `passorder()`，常用值包括 `11/FIX_PRICE`、`5/LATEST_PRICE`、`44/MARKET_PEER_PRICE_FIRST`、`43/MARKET_SH_CONVERT_5_LIMIT`、`47/MARKET_SZ_CONVERT_5_CANCEL`。

`get_full_tick/get_ticks` 的 `codes` 参数支持两种写法：传合约代码如 `["600000.SH", "000001.SZ"]` 查询指定标的；传市场代码如 `["SH", "SZ"]` 查询全市场全推快照。

注意：兼容层的 `xtdata.get_full_tick(codes)` 默认不再通过 RPC 现拉全市场行情。客户端会把需求写入 Redis，10 秒内持续续约；大 QMT 在 `adjust` 中刷新活跃需求到 Redis 快照：**个股列表需求**按 `full_tick_refresh_interval_seconds`(默认 0.5s)快刷，**市场代码需求**(`SH/SZ/BJ/HK` 全市场)按 `full_tick_market_refresh_interval_seconds`(默认 3s)慢刷，避免每个快 tick 都传 5 万条数据；客户端只读取新鲜快照。个股列表若首次缓存未命中，会回退一次 live RPC(~ms)避免硬等；市场代码未命中则只抛超时、不 live 拉全市场。

## 实现文件

- `src/bigqmt_signal_trader/redis_rpc.py`：RPC 协议、订阅服务、外部客户端 helper。
- `src/bigqmt_signal_trader/xtquant_compat.py`：MiniQMT 风格客户端兼容层。
- `src/xtquant/`：可选的 `xtquant` import shim，用于最终替换老 import。
- `src/bigqmt_signal_trader_strategy.py`：在 `init` 中启动 RPC，在 `adjust/handlebar` 中处理请求队列。
- `src/bigqmt_signal_trader_redis_rpc_runtime.py`：大 QMT 策略入口，默认不消费交易信号，只启用 RPC 和持仓同步。
- `tests/bigqmt_signal_trader/test_redis_rpc.py`：RPC 单测。

## 运行方式

把源码同步到 QMT 的 `python` 目录：

```powershell
$srcPkg = '<REPO_ROOT>\src\bigqmt_signal_trader'
$dstPkg = '<QMT_PYTHON_DIR>\bigqmt_signal_trader'
Get-ChildItem -LiteralPath $srcPkg -Force | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination $dstPkg -Recurse -Force
}

Copy-Item -LiteralPath '<REPO_ROOT>\src\bigqmt_signal_trader_strategy.py' `
  -Destination '<QMT_PYTHON_DIR>\bigqmt_signal_trader_strategy.py' `
  -Force

Copy-Item -LiteralPath '<REPO_ROOT>\src\bigqmt_signal_trader_redis_rpc_runtime.py' `
  -Destination '<QMT_PYTHON_DIR>\bigqmt_signal_trader_redis_rpc_runtime.py' `
  -Force
```

QMT 本地私有配置文件：

```python
# <QMT_PYTHON_DIR>\bigqmt_signal_trader_local_config.py
# coding: utf-8

BIGQMT_ACCOUNT_ID = "你的资金账号"

BIGQMT_REDIS_CONFIG = {
    "host": "YOUR_REDIS_HOST",
    "port": 6379,
    "db": 5,
    "username": "",
    "password": "...",
    "rpc_allow_order_methods": False,
    "full_tick_cache_enabled": True,
    "full_tick_demand_ttl_seconds": 10,
    "full_tick_cache_ttl_seconds": 10,
    "full_tick_refresh_interval_seconds": 3,
    "full_tick_max_requests": 8,
}
```

这个文件含账号和 Redis 密码，只放 QMT 本地目录，不提交。

QMT 策略编辑器内容：

```python
#coding:gbk
import sys
import os
import importlib

_qmt_path = os.path.dirname(os.path.abspath(globals().get('__file__', '')))
if not _qmt_path:
    _qmt_path = 'D:/YOUR_QMT_PYTHON_DIR'
if _qmt_path not in sys.path:
    sys.path.insert(0, _qmt_path)

try:
    import bigqmt_signal_trader.redis_rpc as _redis_rpc
    _redis_rpc = importlib.reload(_redis_rpc)
except Exception:
    pass

try:
    import bigqmt_signal_trader_strategy as _strategy
    try:
        _strategy.reset_app()
    except Exception:
        pass
    _strategy = importlib.reload(_strategy)
except Exception:
    pass

import bigqmt_signal_trader_redis_rpc_runtime as _runtime
_runtime = importlib.reload(_runtime)

try:
    from bigqmt_signal_trader_local_config import BIGQMT_REDIS_CONFIG
    _runtime.configure_runtime_redis(BIGQMT_REDIS_CONFIG)
except Exception:
    pass

try:
    from bigqmt_signal_trader_local_config import BIGQMT_ACCOUNT_ID
    _runtime.configure_runtime_account(BIGQMT_ACCOUNT_ID)
except Exception:
    pass

try:
    _runtime.bind_runtime_api(
        passorder_func=passorder,
        cancel_func=cancel,
        get_trade_detail_data_func=get_trade_detail_data,
    )
except NameError:
    pass

init = _runtime.init
handlebar = _runtime.handlebar
adjust = _runtime.adjust
order_callback = _runtime.order_callback
deal_callback = _runtime.deal_callback
```

不要勾选“启动本地 python”。

## Redis 协议

### RPC 请求/响应

请求 channel：

```text
bigqmt:rpc:req:{account_id}
```

请求 payload：

```json
{
  "schema_version": 1,
  "request_id": "req-001",
  "account_id": "YOUR_ACCOUNT_ID",
  "method": "get_positions",
  "params": {},
  "reply_channel": "bigqmt:rpc:resp:YOUR_ACCOUNT_ID:req-001",
  "reply_key": "bigqmt:rpc:resp:YOUR_ACCOUNT_ID:req-001",
  "ttl_seconds": 60
}
```

响应会同时写入：

```text
bigqmt:rpc:resp:{account_id}:{request_id}
```

并 publish 到同名 channel。

响应格式：

```json
{
  "schema_version": 1,
  "request_id": "req-001",
  "account_id": "YOUR_ACCOUNT_ID",
  "method": "get_positions",
  "ok": true,
  "data": {},
  "error": "",
  "handled_at": "2026-07-01 10:30:00"
}
```

### get_full_tick 需求驱动缓存

客户端调用 `xtdata.get_full_tick(codes)` 时会写入需求：

```text
bigqmt:full_tick:demand:{account_id}
```

其中 hash field 是规范化代码集合的 request id，value 包含：

```json
{
  "request_id": "...",
  "codes": ["SH", "SZ"],
  "requested_at_ts": 1780000000.0,
  "expires_at_ts": 1780000010.0,
  "cache_ttl_seconds": 10
}
```

大 QMT 每轮刷新后写入快照：

```text
bigqmt:full_tick:cache:{account_id}:{request_id}
```

快照 Redis key 的 TTL 默认是 10 秒；客户端还会校验 `updated_at_ts`，超过 `cache_ttl_seconds` 的快照不会返回。第一次调用如果还没有快照，客户端默认最多等待 `3.5s` 等下一轮大 QMT 刷新；**个股列表**仍然没有新快照时回退一次 live RPC(`get_full_tick`)以避免冷启动硬停；**市场代码**(`SH/SZ/BJ/HK`)则抛出超时、不回退 live 拉全市场。

## 外部调用示例

```python
import sys
import redis

sys.path.insert(0, r"<REPO_ROOT>\src")

from bigqmt_signal_trader.redis_rpc import call_redis_rpc

r = redis.Redis(
    host="YOUR_REDIS_HOST",
    port=6379,
    db=5,
    username="",
    password="...",
)

response = call_redis_rpc(
    r,
    account_id="YOUR_ACCOUNT_ID",
    method="get_positions",
    params={},
    timeout_seconds=3,
)

print(response)
```

## 延迟与轮询节奏

读 RPC 的主要延迟来源不是 Redis 传输，而是**服务端的队列排空节奏**：订阅线程只把请求塞进 `pending` 队列，真正调用 QMT 的 `drain_pending` 只在 `adjust/handlebar` 里跑，而 `adjust` 由 `run_time("adjust", schedule_adjust_interval)` 触发。因此除 `ping` 外的每个方法，最多要等一个 `schedule_adjust_interval` 才被执行。

- `schedule_adjust_interval`：默认 `"500nMilliSecond"`，可在 `BIGQMT_REDIS_CONFIG` 里调（如 `"1000nMilliSecond"`/`"200nMilliSecond"`）。降低它按比例减少队列等待。
- **务必在真机验证 `run_time` 真按该间隔触发**：启动后每 ~10 秒会打印一行 `adjust cadence: ticks=.. avg=.. min=.. max=..`，看 `avg` 是否贴近你设的间隔。若被 QMT 静默钳制（例如仍是 ~1s/3s），说明该间隔未生效，延迟不会下降。
- 若 `run_time` 不可用或注册失败，会打印 `WARNING ... falls back to bar cadence`，此时排空退化到 bar 回调节奏（可能到分钟级），需要排查。

提高 `adjust` 频率会增加策略线程负担（`tick_app`、full_tick 刷新也在其中），并可能挤占 order/trade 回调——上线后一并观察回调延迟。

## 安全约束

- Pub/Sub 线程只负责接收消息，不直接调用 QMT API。
- QMT API 调用在 `adjust/handlebar` 中通过队列处理，避免在 Redis 订阅线程里碰 QMT 对象。
- 默认只读，远程下单关闭。
- 账号不匹配会拒绝请求。
- 响应写 Redis key 并设置 TTL，方便调用端超时后排查。

## 本地测试

```powershell
cd <REPO_ROOT>
python -B -m unittest discover -s tests\bigqmt_signal_trader
```

当前结果：

```text
Ran 41 tests
OK
```

