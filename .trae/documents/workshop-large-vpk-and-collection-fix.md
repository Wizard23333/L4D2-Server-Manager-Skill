# Workshop 大体积 VPK 下载稳健性 + 集合(Collection)自动展开 方案

## Summary

修复"安装某个 Workshop ID（如 `3220375446`）时只得到一个损坏/不完整 VPK，导致地图整体不可用"的问题。经 Steam API 实测确认该问题包含**两类根因**，本方案两者都处理：

1. **大文件下载不稳健 + 损坏校验不严（主因，已实测复现）**：`3220375446` 实为单个 **984 MB** 大 VPK（`mapaliminal.vpk`，内含 Party/Poolrooms 等多章节），并非集合。下载在 CDN 中途断连/截断时，损坏文件仍可能通过仅校验前 4 字节魔数的 `assert_vpk_file`，被复制进 `addons/`，进游戏后整图不可用（面板上表现为 `VPK data is truncated: sound/sound.cache`）。
2. **真·集合无法自动展开（次因）**：若用户输入的是 Steam 集合 ID（含多个子项），当前代码写死 `itemcount=1` 且只取 `[0]`，从不调用 `GetCollectionDetails`，集合外的多子项地图会静默只装一个。

方向与策略已由用户确认：**两者都做** + **严格校验 + 自动重试**（校验/下载失败自动重试若干次；最终仍失败则 job 判失败且绝不把损坏文件落地到 addons）。

## Current State Analysis

调用链（两层进程）：
- 前端/API → `create_install_job` → `create_catalog_install_job`（[app.py#L1907](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1907)）→ 线程跑 `install_catalog_bundle_job`（[app.py#L1822](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1822)）
- 逐个 install_id → `run_install_command`（[app.py#L1648](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1648)）→ 子进程 `sudo l4d2-webctl install-workshop <kind> <id>`
- webctl 内：`install_workshop`（[l4d2-webctl#L708](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/l4d2-webctl#L708)）→ `fetch_workshop_details`（[L284](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/l4d2-webctl#L284)）→ `download_file`（[L309](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/l4d2-webctl#L309)）→ `assert_vpk_file`（[L771](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/l4d2-webctl#L771)）→（map 时）`extract_map_package`（[L373](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/l4d2-webctl#L373)）

现存缺陷：
- **`assert_vpk_file` 只读前 4 字节魔数**，不校验整体结构/尾部完整性。截断文件可通过。
- **`download_file` 的完整性校验依赖 `Content-Length`/`file_size`**（[L343-346](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/l4d2-webctl#L309)）：当 CDN 未回 Content-Length 且 `file_size` 为 0 时无任何校验，截断文件被接受。
- **无断点续传、无整次下载重试**：`open_with_retries`（[L269](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/l4d2-webctl#L269)）只重试"建立连接"，连接建立后流中途断开仅触发一次失败，不重试整次下载；984 MB 大文件失败率高。
- **集合无探测**：`fetch_workshop_details`、`workshop_detail_result`（[app.py#L1461](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1461)）均 `itemcount=1` 只取 `[0]`，从不查 `GetCollectionDetails`/`num_children`。多子项来源仅靠硬编码白名单 `KNOWN_CATALOG_ITEMS`（[app.py#L151](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L151)，如"广西灵山""Yama"）。
- VPK 解析逻辑已存在于 [vpk_extract.py](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/vpk_extract.py)（`iter_entries` 能遍历目录树、计算 `data_start`/`entry_offset`/`entry_size`），可直接复用做"结构完整性校验"。

实测依据（本机已用 curl 验证）：
- `GetCollectionDetails(3220375446)` → `result: 9`（非集合）。
- `GetPublishedFileDetails(3220375446)` → `file_size: "984026042"`，`filename: "mapaliminal.vpk"`，单文件。

## Proposed Changes

### 改动 1：新增 VPK 结构完整性校验（vpk_extract.py）

**File**: [vpk_extract.py](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/vpk_extract.py)

**What/Why**: 复用 `iter_entries` 增加一个"只校验不落地"的 `verify` 模式，遍历所有 entry，确认每个 inline entry 的 `data_start + entry_offset + entry_size` 都 ≤ 文件实际字节数，从而在**复制进 addons 之前**就能发现截断/损坏。这是拦截损坏文件的核心。

**How**:
- 新增 `verify(vpk_path)` 函数：打开文件取实际大小 `file_len = os.path.getsize`；调用 `iter_entries` 遍历；对 `archive_index == INLINE_ARCHIVE` 的 entry 校验 `data_start + entry_offset + entry_size <= file_len`，否则 `fail("VPK is truncated: <name> needs <end> bytes but file is <file_len>")`；遍历过程本身若 `iter_entries` 抛 truncated（tree 截断）也会失败。统计 entry 数，最后 `print(f"verified <n> entries, <file_len> bytes")`。
- `main()` 支持两种调用：`vpk_extract.py --verify <input.vpk>`（仅校验）与现有 `vpk_extract.py <input.vpk> <target_dir>`（解包，保持不变）。
- 兼容性：保持 Python 3.8（不使用 3.9+ 语法），不引入新依赖。

### 改动 2：下载稳健性 + 严格校验 + 自动重试（l4d2-webctl）

**File**: [l4d2-webctl](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/l4d2-webctl)

**What/Why**: 让大文件下载在中途断连后能整次重试（含 HTTP Range 断点续传），并在落地 addons 前强制结构校验；任何环节失败都重试，超出次数才 `fail`，且失败时清理临时文件，绝不把损坏文件 `copy2` 到 `ADDONS_DIR`。

**How**:
- **`download_file` 改造**（[L309](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/l4d2-webctl#L309)）：
  - 外层包一个 `attempts`（默认 4 次）重试循环。每次失败（连接异常、中途断流导致 `downloaded != expected`）后指数退避（`min(2**(n-1), 8)` 秒）重试。
  - **断点续传**：保留已下载的 `.part` 文件，重试时带 `Range: bytes=<已下载>-` 续传；服务器返回 206 则追加写入，返回 200（不支持 Range）则从头覆盖重写。
  - **完整性判定收紧**：以 `expected = int(expected_size or 0)` 为准；若 `expected > 0` 必须 `downloaded == expected` 才算成功；当 `expected == 0` 且无 Content-Length 时，记一条 warning 消息（无法按大小校验，交由后续 VPK 结构校验兜底），不直接当成功大小。
  - 仍保留逐 0.5s 的 `emit("progress", ...)` 上报，重试时在 message 注明 `retry n/N`。
- **`install_workshop` 改造**（[L708](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/l4d2-webctl#L708)）：
  - 下载 + 校验整体作为一个可重试单元（默认 3 次）：`download_file` → `assert_vpk_file`（魔数）→ **`run_vpk_verify(download_target)`（新增，调用 `vpk_extract.py --verify` 结构校验）**。任一步失败则删除 `.part`/`download_target` 并重试整个下载；全部用尽才 `fail`。
  - 仅在校验全部通过后，才执行 `extract_map_package`（map）与 `shutil.copy2(download_target, destination)`，确保**损坏文件永不落地 addons**。
  - 新增辅助 `run_vpk_verify(path)`：`subprocess.run(["/usr/bin/python3", str(VPK_EXTRACTOR), "--verify", str(path)], ...)`，非 0 退出则抛错触发重试。
  - `emit` 增加阶段消息（如 `verifying`），便于前端/日志观察。
- **磁盘安全**：下载前可选检查 `DOWNLOAD_DIR` 所在分区剩余空间是否 ≥ `file_size`（若 `file_size>0`），不足则 `fail` 明确提示，避免写半截。（实现为轻量 `shutil.disk_usage` 检查，失败仅作 fail 提示，不改其它逻辑。）

### 改动 3：集合(Collection)自动探测与展开（app.py）

**File**: [app.py](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py)

**What/Why**: 当用户输入/安装的是 Steam 集合 ID 时，自动用 `GetCollectionDetails` 展开为子项 ID 列表，复用现有 `install_catalog_bundle_job` 的"多包串行安装"链路逐个安装，避免只装一个。白名单仍作为 fallback 优先级最高，保持现有行为稳定。

**How**:
- 新增常量 `STEAM_COLLECTION_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"`（紧邻 `STEAM_DETAILS_URL` 定义，[app.py#L120](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L120)）。
- 新增函数 `fetch_collection_children(collection_id) -> list[str]`：POST `collectioncount=1&publishedfileids[0]=<id>`，解析 `response.collectiondetails[0]`；若 `result == 1` 且含 `children`，按 `children[].sortorder` 排序返回 `children[].publishedfileid` 列表；否则（如实测的 `result: 9`）返回 `[]`。网络异常吞掉返回 `[]`（不阻断主流程，退化为单项安装）。
- 修改 `create_catalog_install_job`（[app.py#L1916](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1916)）的 `item_ids` 解析优先级为：
  `install_ids（前端显式传入）` → `known_install_ids（白名单）` → **`fetch_collection_children（新增，仅 workshop 源时调用）`** → `[item_id]`。
  即仅当前两者都为空且来源是 workshop 时，才尝试集合展开；展开成功（非空）则用子项列表，失败/非集合则维持原 `[item_id]` 单项行为。
- `workshop_detail_result`（[app.py#L1461](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1461)）增强：查询详情时，若 `GetPublishedFileDetails` 无 `file_url` 但 `fetch_collection_children` 返回非空，则把该条目标记为可安装的集合（`installable=True`，`install_ids=<子项>`，`size="<n> packages"`，reason 说明"集合，将安装 n 个子项"），让搜索结果/前端能携带 `install_ids` 下发。保持对普通单项条目的现有展示不变。

### 改动 4（可选，低优先级）：记录整组关系

**File**: [app.py](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py) `install_catalog_bundle_job`（[L1867](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1867)）

**What/Why**: 当前每条 package record 的 `install_ids` 只含自身 ID，多包战役的整组关系不落库。可在 `total_items > 1` 时把完整 `item_ids` 写入每条 record 的 `install_ids`，便于异机迁移整组复现。

**How**: 将 `register_installed_package(..., [current_id])` 在 `total_items > 1` 时改为传入完整 `item_ids`。**此项默认不实施**，仅在前三项验证通过后视需要追加，避免一次改动过大。

## Assumptions & Decisions

- **`3220375446` 是单个大 VPK 而非集合**（已实测）。本案例由改动 1+2 解决；集合展开（改动 3）面向"用户确实输入集合 ID"的场景，二者互补。
- **下载用纯 HTTP（不引入 steamcmd）**：维持现有最小依赖与 Python 标准库实现（符合项目约定），通过 Range 续传 + 整次重试 + 结构校验提升稳健性。
- **重试次数**：下载层 4 次、下载+校验单元 3 次（指数退避，封顶 8s）。可在实现时设为常量便于调整。
- **失败即不落地**：校验任何一步失败都清理临时文件并最终 `fail`，addons 目录只接收校验通过的文件（符合用户"严格校验"选择）。
- **集合展开仅对 workshop 源**：gamemaps 无此 API；且 `create_catalog_install_job` 现有约束 `source != "workshop"` 不允许多项（[L1917](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1917)）保持不变。
- **Python 3.8 兼容**：服务器为 3.8.10，全部新代码避免 3.9+ 语法（如 `removeprefix`）。
- **部署前备份**：按项目约定，部署 `app.py`/`l4d2-webctl`/`vpk_extract.py` 前创建带时间戳备份，可回滚。

## Verification Steps

1. **本地静态检查**：对 `app.py`、`vpk_extract.py` 做 `python -m py_compile`；`l4d2-webctl` 同样语法检查。
2. **VPK 校验单测（服务器）**：对一个已知完好的 VPK 运行 `vpk_extract.py --verify` 应通过；对人为截断的副本（`head -c <小于全长> good.vpk > bad.vpk`）应报 truncated 并非 0 退出。
3. **集合探测函数**：在服务器 `python3 -c` 调用 `fetch_collection_children`，对真集合 ID 返回非空子项、对 `3220375446` 返回 `[]`。
4. **端到端大文件安装**：在面板用 Workshop ID `3220375446` 触发安装，观察 job 经历 `downloading → verifying → extracting → finished`；若中途断连应看到 `retry n/N` 并最终成功；若始终损坏则 job 失败且 addons 中无该 vpk（不残留损坏文件）。
5. **集合端到端**：用一个真实集合 ID 安装，确认展开为 N 个子项、逐个安装、job `items_total == N`。
6. **回归**：普通单项 Workshop/GameMaps 安装行为不变；白名单条目（广西灵山/Yama）仍走白名单 install_ids。
7. **浏览器复核**：经 SSH 隧道在面板 Install & Jobs 区核对 job 进度与最终状态展示正常。

## Rollout

- 本地改三文件 → 备份服务器现有 `app.py`/`l4d2-webctl`/`vpk_extract.py`（时间戳）→ scp 上传 → `py_compile`/语法校验 → 替换 + 正确属主权限 → 重启 `l4d2-manager-web` → 按 Verification 验证 → 经隧道浏览器复核。
