# Tasks

- [x] Task 1: 新增描述兄弟包发现函数并接入发现链
  - [x] SubTask 1.1: 在 `app.py` 新增 `fetch_description_sibling_ids(workshop_id, kind)`：调用匿名 `STEAM_DETAILS_URL` 取 `description`，用正则解析 `id=<数字>` / `filedetails/?id=<数字>` 引用，去重、剔除自身、限制数量上限，对每个候选调用 `resolve_single_workshop_download(cid, kind)` 校验能否解析出可下载 `file_url`，返回 `[主ID] + 校验通过的兄弟ID`（无有效兄弟时返回 `[]`）。
  - [x] SubTask 1.2: 在 `create_install_job` 的 install_ids 解析中，在 curated / collection / meta.children 之后追加描述兄弟包兜底。
  - [x] SubTask 1.3: 在 `create_catalog_install_job` 的 `item_ids` 解析链（`fetch_collection_children` / `fetch_required_children` 之后、退回 `[item_id]` 之前）追加描述兄弟包兜底。
  - [x] SubTask 1.4: 在 `workshop_expected_parts` 的解析链（collection / meta.children 之后）追加描述兄弟包兜底，使预览 parts 与实际安装一致。
- [x] Task 2: 为 SGC 增加 curated 条目
  - [x] SubTask 2.1: 在 `KNOWN_CATALOG_ITEMS` 追加 `Left 4 SGC Beta v2.2`（`id: "1713617501"`, `install_ids: ["1713617501","1713621105"]`, `kind: "map"`, 合理 aliases 与 summary）。
- [x] Task 3: 多包地图安装后无 .bsp 告警
  - [x] SubTask 3.1: 在 `install_catalog_bundle_job` 注册包之后，对 `kind=map` 且 `total_items > 1` 的分组，统计整组 `vpk_inventory()` 内的 `maps`；若整组无任何 `.bsp`，向 `messages` 追加一条可读告警（提示该战役可能缺少含地图的依赖包、需补装）。
- [x] Task 4: 版本标记与打包 fix 版本
  - [x] SubTask 4.1: 更新面板版本标记（`Handler.server_version` 提升到带 fix 的版本号，如 `L4D2Manager/0.2`），便于确认修复已部署。

# Task Dependencies
- Task 1 SubTask 1.2/1.3/1.4 依赖 SubTask 1.1。
- Task 2、Task 3、Task 4 相互独立，可与 Task 1 并行。

# Tasks（第 2 轮：VPK 目录树尾部脏字节修复）

- [x] Task 5: 修复 VPK 目录树解析，按边界+终止符收尾，避免把尾部脏字节误判为分卷
  - [x] SubTask 5.1: 在 `deploy/l4d2-manager-web/vpk_extract.py` 的 `iter_entries` 中记录目录树边界 `tree_end = header_size + tree_size`；在读取每个 extension/path/filename 的 null 字符串之前，若 `handle.tell() >= tree_end` 则停止解析（视为目录树结束），不再向后读取。
  - [x] SubTask 5.2: 在读取 18 字节目录项后校验规范终止符：`_term != 0xFFFF` 时视为到达目录树末尾（遇到非规范尾部字节），停止解析而非继续/报错；确保仅保留合法条目。
  - [x] SubTask 5.3: 保持对“真正多分卷”的既有行为：对**边界内**合法条目仍执行 `archive_index != INLINE_ARCHIVE` 判定并 `fail("Multi-part VPK archives are not supported by this extractor")`。修复只影响“边界外/终止符非法”的伪条目。
  - [x] SubTask 5.4: 同步修复 `deploy/l4d2-manager-web/l4d2-webctl` 内的 `vpk_maps()` 与 `vpk_entries()` 两个内联 VPK 解析器（同样加入 `tree_end` 边界与 `_term==0xFFFF` 收尾判定），避免面板列图/清单侧对同类包解析出错或误报。
  - [x] SubTask 5.5: `python3 -m py_compile vpk_extract.py l4d2-webctl` 通过；对本地/服务器上的 b包 `3743875149` 运行 `--verify` 与 `extract` 应成功，条目数为 5566，且对真正多分卷样本仍报错（用构造/既有逻辑推理验证）。
- [x] Task 6: 部署 fix 并端到端验证江门新会三包安装
  - [x] SubTask 6.1: 将修复后的 `vpk_extract.py` 与 `l4d2-webctl` 部署到服务器（`/opt/l4d2-manager-web/vpk_extract.py`、`/usr/local/bin/l4d2-webctl`），备份原文件，`py_compile` 校验，权限/属主正确。
  - [x] SubTask 6.2: 以面板真实调用方式（`sudo -n l4d2-webctl install-workshop map <id>`）分别安装 `3743875149`、`3743877283` 验证 `--verify`+解包成功；确认切图列表出现江门新会各章节 `.bsp`。
  - [x] SubTask 6.3: 提升面板版本标记到新的 fix 版本号（`app.py` 的 `Handler.server_version`，如 `L4D2Manager/0.3`）并部署，便于确认修复已上线。

# Task Dependencies（第 2 轮）
- Task 6 依赖 Task 5（先修复解析器再部署验证）。
- Task 5 各 SubTask 可并行编辑，SubTask 5.5 依赖 5.1-5.4。
