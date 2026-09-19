## Round 1

- 完成任务：修复面板多包地图安装逻辑，产出 fix 版本（L4D2Manager/0.2）。所有 tasks.md 任务与 checklist.md 检查项均已勾选，`py -3 -m py_compile app.py` 通过。
- 根因：SGC 这类多包地图，含 `.bsp` 的第二包只在 Workshop 描述文本里以 `id=1713621105` 引用，既非 collection children 也非 GetDetails children，且服务器无 `STEAM_WEB_API_KEY`，导致原发现链只装到无地图的资源包。
- 关键实现：
  - 新增 `fetch_description_sibling_ids(workshop_id, kind)`（app.py 行 1598-1637）：匿名 `STEAM_DETAILS_URL` 取 description，正则解析 `id=`/`filedetails/?id=` 引用，去重剔除自身、上限 8，逐个 `resolve_single_workshop_download` 校验后返回 `[主ID]+有效兄弟ID`，无有效兄弟返回 `[]`。不依赖 API key。
  - 作为发现链最后兜底接入三处：`workshop_expected_parts`（行 1921-1925，命中时 collection=True）、`create_catalog_install_job`（行 2508-2511，退回 [item_id] 之前）、`create_install_job`（行 2572-2575）。前序来源产出多包时不触发描述解析，避免误报与多余请求。
  - `KNOWN_CATALOG_ITEMS` 新增 `Left 4 SGC Beta v2.2`（行 252-264，`install_ids: ["1713617501","1713621105"]`），保证按 ID/名称确定性装两个包。
  - `install_catalog_bundle_job` 新增多包 map 安装后无 `.bsp` 告警（行 2459-2470），整组无地图时向成功消息追加中文提示补装。
  - 版本号 `Handler.server_version` 由 `L4D2Manager/0.1` 升到 `L4D2Manager/0.2`（行 5273）。
- 决策：描述解析仅作为最后兜底、且对每个候选做在线可下载校验，兼顾发现能力与零误报；SGC 同时加 curated 条目以获得确定性行为。
- 变更文件：`deploy/l4d2-manager-web/app.py`（唯一改动文件，未部署到服务器）。

## Round 2

- 完成任务：Task 5、Task 6 及全部 SubTask 均已勾选；checklist 第 2 轮 9 条全部验证通过。修复了江门新会 `3743921409` 通过面板安装失败的真正根因，并部署 fix 版本（L4D2Manager/0.3），端到端重装三包成功。
- 根因（第 2 轮真实故障）：多包发现本身正常（SGC 两包已成功），但江门新会安装在第 2 包 `map_3743875149_0.51_Bata_b.vpk` 的 `--verify` 阶段抛 `Multi-part VPK archives are not supported by this extractor`，整组 3 包中断。b 包（v1 VPK，`tree_size=239195`）目录树后残留脏字节，而 `vpk_extract.py`/`l4d2-webctl` 的解析循环既不按 `tree_size` 边界停止、也不校验规范恒为 `0xFFFF` 的 2 字节终止符，把树后二进制误解析成 10 条 `archive_index` 为大数、文件名乱码、size 达 GB 级的伪条目，命中 `archive_index != 0x7FFF` 被判为多分卷。实际 5566 条合法 inline 条目数据完整、无分卷。
- 关键实现：
  - `vpk_extract.py` 的 `iter_entries` 加入 `tree_end = header_size + tree_size` 边界（三层 while 每层开头 `if handle.tell() >= tree_end: break`），读取 18 字节目录项后 `if _term != 0xFFFF: return` 收尾；`extract`/`verify` 中对**边界内**合法条目仍保留 `archive_index != INLINE_ARCHIVE` 的多分卷报错（无回归）。
  - `l4d2-webctl` 的 `vpk_maps()` 与 `vpk_entries()` 同步加入 `tree_size`/`tree_end` 边界 + `_term != 0xFFFF` 收尾（`return maps`/`return entries`）。
  - `Handler.server_version` 由 `L4D2Manager/0.2` 升到 `L4D2Manager/0.3`。
- 验证：本地 `py_compile app.py vpk_extract.py l4d2-webctl` 通过；部署到服务器（原文件备份 `*.bak-<ts>`、属主 `l4d2web`/`root` 权限正确、service active、HTTP 头 `Server: L4D2Manager/0.3`）。以面板真实调用 `sudo -n l4d2-webctl install-workshop map <id>` 重装三包全部 rc=0：主包 `3743921409`（774MB）、b 包 `3743875149`（371MB，此前失败包现 verify/extract 成功）、a 包 `3743877283`（689MB）。`/opt/l4d2/left4dead2/maps/` 出现全部 5 个章节 `.bsp`：`jiangmmenxinhuai_1`、`_x2`、`_2_1_d`、`_3_1`、`jiangmenxinuai_xuxi`。
- 决策：以“目录树声明边界 + 规范终止符”双重收尾判定作为收敛条件，最小改动且不影响真正多分卷 VPK 的既有拒绝行为；本轮采用 Path B，在既完成的 `fix-multipart-map-install` spec 上追加第 2 轮任务而非新建 spec。
- 变更文件：`deploy/l4d2-manager-web/vpk_extract.py`、`deploy/l4d2-manager-web/l4d2-webctl`、`deploy/l4d2-manager-web/app.py`（均已部署到服务器）。
