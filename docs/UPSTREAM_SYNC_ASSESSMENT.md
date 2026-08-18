# 上游同步评估（Upstream Sync Assessment）

> 评估日期：2026-08-18
> 当前仓库：`kevin249/xtquant_big_convert` @ `fb79428`（main，2026-07-21）
> 上游仓库：`litaolemo/xtquant_big_convert` @ `fa480bd`（main，2026-08-17，tag `v0.2.1`）

---

> ## ✅ 已执行（2026-08-18）
>
> 本评估的建议已落地：`upstream/main` (`fa480bd`, v0.2.1) 已合并进本仓库，合并 commit `c7023a9`。
> - 冲突 **0 个**，与评估预测一致
> - 合并后 `run_all_tests.py`：**298 passed / 4 skipped / 0 failed**
> - 合并结果与 `upstream/main` 的差异**仅有本文件一个**（`git diff upstream/main HEAD` → 1 file changed）
>
> 下文保留同步前的评估原文。**第 5 节的 3 个风险项仍需在部署侧处理**（尤其 R1：国泰环境需设
> `BIGQMT_LOG_ENABLED=0`），第 6 节的执行方案已完成，验收清单第 2–6 项仍待在实际 QMT 环境中核对。

---

## 1. 结论摘要

| 项目 | 结论 |
|------|------|
| 原（上游）git | **`litaolemo/xtquant_big_convert`** — 与本仓库共享 git 历史，首个 commit 同为 `cad2be9` |
| 落后程度 | **落后 70 个 commit**（2026-07-21 → 2026-08-17），跨 `v0.2.0` + `v0.2.1` 两个版本 |
| 领先程度 | 领先 1 个 commit（`fb79428`），但它是**空合并**——`git diff f90b46c HEAD` 为空 |
| 本地独有内容 | **无**。当前工作树与上游 `f90b46c` 逐字节一致 |
| 我们的贡献 | 4 个 commit（含「增加国泰证券支持」`1dc43cd`）**已被上游经 PR #14 合并** |
| 合并冲突 | **0 个**（已实机试合并验证） |
| 合并后测试 | **302 个测试：298 通过 / 4 跳过 / 0 失败** |
| 变更规模 | 81 个文件，**+17,211 / −374** 行 |
| 文件删除/重命名 | **无**，纯增量 |
| **建议** | **可以直接同步，风险很低**；执行前按第 5 节处理 3 个注意事项 |

---

## 2. 两库关系的事实依据

不是猜测，是 git 历史证据：

```
共同祖先（merge-base）: f90b46c  "Release ZMQ port on QMT restart"  2026-07-20
首个 commit 双方相同:    cad2be9  "Initial Big QMT Redis RPC bridge" 2026-07-01
```

本仓库的 4 个 commit 全部已在上游 main 上：

| commit | 作者 | 是否在上游 |
|--------|------|-----------|
| `1dc43cd` 增加国泰证券支持（zmq 替代 redis、不写本地文件/日志） | kevin kong | ✅ 已合并 |
| `a39752c` fast | kevin kong | ✅ 已合并 |
| `0403a49` Add isolated ZMQ backtest bridge | kevin kong | ✅ 已合并 |
| `f90b46c` Release ZMQ port on QMT restart | kevin kong | ✅ 已合并 |
| `fb79428` Merge ZMQ backtest bridge | kevin kong | ❌ 仅本地（**空合并，无内容差异**） |

上游以 `634d214 Merge pull request #14 from kevin249/codex/zmq-backtest-bridge` 收编了这批工作。
**因此同步不存在「把本地改动合丢」的风险——本地没有任何独有改动。**

---

## 3. 上游新增了什么（v0.2.0 / v0.2.1）

### 3.1 新增能力（Features）

| 模块 | 说明 | 规模 |
|------|------|------|
| **FormulaServer 直连快通道** `formula_server.py` | 绕过 RPC 桥和 QMT python 线程 GIL，直连大 QMT 内置 C++ 行情服务（58600 端口）。参考/历史类读取 **~0.07ms**，对比 redis RPC 的 ~13ms（约 180×）。默认开启，任何 miss 自动回落 RPC | 718 行 |
| **全推行情真推送** `subscribe_whole_quote` | 服务端引用计数 + PUB/SUB 数据面（redis/zmq）+ 客户端心跳 + 推送静默检测 + 服务端重启恢复，对齐 MiniQMT 原生语义 | `quote_push_channel.py` 270 + `quote_subscription_manager.py` 258 + `whole_quote_session.py` 204 |
| **异步回报回调全链路** | `on_account_status` / `on_order_stock_async_response` / `on_stock_order` / `on_stock_trade` / `on_order_error` / `on_cancel_error` / `on_cancel_order_stock_async_response`，实盘验证 | `xtquant_compat.py` +955 |
| **19 个新客户端方法** | `query_stock_asset_async` / `query_stock_positions_async` / `query_stock_orders_async` / `query_stock_trades_async` / `query_credit_*_async`（4 个）/ `query_ipo_data_async` / `query_new_purchase_limit_async` / `smt_appointment_async` / `rpc_call` / `supports` 等 | — |
| **完整 xtconstant 枚举** | 91 个常量全量覆盖，值对齐原生 MiniQMT | `xtconstant.py` +114 |
| **文件日志系统** `logging_setup.py` | 按天轮转、保留 7 天、双输出（文件 + QMT 面板）、线程安全、永不抛异常 | 171 行 |
| **无 redis 版本** `bigqmt_no_redis/` | 自包含 ZMQ transport + 无 redis DRYRUN，解决券商白名单拦截 `import redis` | 711 行 |
| **qmt-trader skill** | 统一 CLI 驱动全部 QMT API，46 个子命令 + 通用 `rpc` 兜底 + 25 个快捷命令 | `scripts/qmt.py` 1,008 行 + SKILL.md + api_reference.md |
| **MiniQMT→BigQMT 转换 skill** | 迁移文档 + 分析/校验脚本 + 策略模板（含 4,411 行策略手册） | `docs/MiniQMT_2_BigQMT-Skill/` |
| **测试体系** | `run_all_tests.py` 统一入口；测试从 **145 → 298** 个（+11 个测试文件），含生产失败场景（返回空/全 0/拒绝）与端到端验证 | — |
| **工程化** | `CHANGELOG.md`、`LICENSE`（MIT）、PyPI 发布（`pip install xtquant-big-convert`）、完整 pyproject 元数据 | — |

### 3.2 关键 Bug 修复（对实盘直接有价值）

- **QMT 自动退出（崩溃系列）**：`ZmqQuotePushChannel.stop()` 跨线程关 SUB socket 触发 Windows signaler abort；另修 `_adjust_phase` / `_publish_response` / `deal_callback` / `forward_*_event` / `sync_positions_app` / `init()` 无异常保护、pending 队列满、`socket_timeout=None` 永久阻塞主线程、`reset_app` 不清理 quote-push（重启泄漏）、exec 事件每次回调新建 redis client（连接池泄漏）。
- **正常下单误报 `on_order_error(-1)`**（Issue #38，v0.2.1）：passorder 提交成功但委托号异步分配，被误判为失败。改为按唯一 `user_order_id`(remark) 匹配回填 `order_sys_id`。
- **`download_history_data` 下不动**（Issue #32）：它是 QMT 全局函数不是 ContextInfo 方法，改走 `qmt_api` 注入。
- **复权数据返回全 0**（front/back）：下载类自动预下载原始数据 + 除权因子；读取类（`get_market_data` / `get_market_data_ex`）检测全 0 自愈重试。
- **卖出方向误判**：QMT 回调 `m_nDirection` 恒为 48，改为仲裁链 `offset_flag > direction > op_type`。
- **`query_orders` / `query_trades` 返回空**：`strategy_name` 过滤不匹配，默认改 `""`。
- **`get_financial_data` 返回 None**：参数顺序颠倒（stock_list / table_list）。
- **`position_events` 内存无限增长**（Issue #21）：xadd 加 `maxlen=2000`。
- **异步回调签名错误**：原生签名是 1 参数（response 带 seq），之前传 2 参数导致 `TypeError` 被吞。
- **重复执行回调**、**客户端 transport 不匹配**（Issue #24）、**ZMQ bind 冲突无提示**等。

---

## 4. 同步可行性验证（已实测）

在隔离 worktree 中真实执行过，不是纸面推演：

```
1) git merge upstream/main            → "Automatic merge went well"，冲突文件数 = 0
2) 合并后 python3 run_all_tests.py    → signal_trader 282 passed / backtest 16 passed
                                         合计 298 passed, 4 skipped, 0 failed ✅
3) git diff --diff-filter=D HEAD upstream/main → 空（上游未删除任何现有文件）
4) git diff --find-renames --diff-filter=R     → 空（无重命名）
```

参照基线：当前仓库自身测试为 **145 passed / 2 skipped**（需装 `pytest pandas DBUtils pyzmq redis`，缺失时会有 9 个环境性失败，与代码无关）。

---

## 5. 风险与注意事项（同步前必看）

### 🔴 R1 — 文件日志与国泰白名单冲突（最需要关注）

上游 v0.2.0 引入 `logging_setup.py`，默认把日志写到 `<qmt_python_dir>/logs`。这与本仓库 `1dc43cd` 的部署前提**方向相反**——该 commit 的原话是「国泰白名单……不让写和读本地文件……本地也不再保存 log」。

缓解情况（已核对源码）：
- 模块会先探测目录可写性（写 `.write_test` 再删），不可写自动回落到 `~/.cache/bigqmt/logs`；
- 全程 `try/except`，「a logging failure must not bring down the strategy」；
- 提供显式开关：**`BIGQMT_LOG_ENABLED=0`**（另有 `BIGQMT_LOG_TO_STDOUT=0`）。

**行动项**：国泰环境同步后，在 QMT 端环境变量设 `BIGQMT_LOG_ENABLED=0`，并实测确认策略不再产生本地文件。

### 🟡 R2 — `strategy_name` 默认值行为变更

`query_stock_orders` 的客户端默认 `strategy_name` 从 `"bigqmt_signal_trader"` 改为 `""`（返回全部委托）。
若现有代码依赖「只返回本策略委托」的旧行为，需**显式传入 `strategy_name`**。

### 🟡 R3 — 上游 4 个未修复的 open issue

同步意味着一并继承这些已知问题：

| # | 标题 | 影响 |
|---|------|------|
| **#44** | `order_stock_async` 实际同步阻塞 QMT 主线程 | 服务端 `_handle_submit_order` 每单 `time.sleep(0.5)`，QMT 主线程串行执行 → **大批量下单不可行**。若有批量下单需求，这是硬伤 |
| **#43** | `server_error` 污染后续查询 | `_last_server_error` 是实例变量且不清除，一次下单失败后，后续无关 RPC 响应会带上这个陈旧错误 → 误报 |
| **#41** | `order_remark` 查询失败的 fallback 机制 | 与 v0.2.1 的委托号回填逻辑相关 |
| **#45** | 国金大 QMT 自动登录 | 需求类，非缺陷 |

注意 #43 / #44 都开在 2026-08-17（v0.2.1 发布当天），即**当前上游 HEAD 尚未修复**。

### 🟢 R4 — 新增可选依赖

| 依赖 | 用途 | 缺失后果 |
|------|------|---------|
| `msgpack` | 全推行情推送的线上编码 | 自动回落 json，功能不受影响 |
| `pymysql` + `DBUtils` | `mysql` transport（extra） | 仅 mysql transport 不可用 |
| `pytest` / `pytest-cov` | `dev` extra | 仅影响跑测试 |

### 🟢 R5 — 仓库体积与授权

- 新增 +17,211 行，其中约 6,900 行是两套 skill 文档/脚本（`qmt-trader/`、`docs/MiniQMT_2_BigQMT-Skill/`）。如不需要 AI skill，可同步后单独删除，不影响运行时。
- 上游新增 **LICENSE（MIT）**，署名 `litaolemo`。本仓库此前无 LICENSE，同步后授权关系明确化。

---

## 6. 执行方案

本地无独有内容，两种方式等价，推荐 A：

**A. 合并（保留本地 merge commit 历史）**

```bash
git remote add upstream https://github.com/litaolemo/xtquant_big_convert
git fetch upstream
git checkout main
git merge upstream/main          # 已验证：0 冲突
python3 run_all_tests.py         # 期望 298 passed / 0 failed
git push origin main
```

**B. 对齐（丢弃空合并 `fb79428`，历史与上游完全一致）**

```bash
git fetch upstream
git checkout main
git reset --hard upstream/main   # 安全前提：git diff f90b46c HEAD 为空，已验证
git push --force-with-lease origin main
```

**同步后建议的验收清单**

1. `python3 run_all_tests.py` → 298 passed / 0 failed
2. 国泰环境：设 `BIGQMT_LOG_ENABLED=0`，确认无本地文件写入（R1）
3. 复核所有 `query_stock_orders` 调用点是否需要显式 `strategy_name`（R2）
4. 若使用批量下单，先评估 #44 的 0.5s/单阻塞是否可接受（R3）
5. 客户端与服务端 `transport` 配置需一致（新版会明确报错，旧版是静默 None）
6. 客户端配置可选新增：`BIGQMT_FORMULA_SERVER_CONFIG`（默认已开启，无需改）、`BIGQMT_QUOTE_CLIENT_ID`、`BIGQMT_DOWNLOAD_WAIT_SECONDS`。所有新键都有默认值，**现有配置文件无需修改即可工作**。

---

## 7. 总体评价

**建议同步，优先级：高。**

- **成本极低**：无本地独有改动、零冲突、无文件删除、配置向后兼容、合并后全量测试绿。
- **收益明确**：修掉一批会导致 **QMT 进程崩溃/自动退出**的缺陷，以及复权全 0、下载失效、卖出方向误判、下单误报错误等直接影响实盘正确性的问题；同时拿到 FormulaServer 快通道（读取 ~180× 提速）与全推行情。
- **唯一需要动手的**是 R1（国泰环境关掉文件日志）；R2 是一行调用检查；R3 是需要知情的已知缺陷，与是否同步无关（不同步同样没有修复）。

拖延同步的代价会随时间上升：上游迭代很快（一个月 70 个 commit），越晚合并越可能出现真实冲突。
