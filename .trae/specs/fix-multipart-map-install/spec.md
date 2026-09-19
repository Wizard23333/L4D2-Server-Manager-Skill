# 修复面板多包地图安装逻辑 Spec

## Why
通过 Web 面板按 Workshop ID 安装多包地图时，若第二个（含 `.bsp` 的）资源包只在 Workshop **描述文本**里被引用（例如 `Left 4 SGC Beta v2.2 (1 of 2)` ID `1713617501` 的描述写着 `Part 2 NEEDED TOO ... id=1713621105`），当前发现链（curated `install_ids` → collection children → GetDetails children）无法找到它，且服务器缺少 `STEAM_WEB_API_KEY`，导致只装到无地图的资源包，切图列表里没有该战役。需要修复这个多包发现缺陷并产出一个 fix 版本。

## What Changes
- 新增「从 Workshop 描述文本解析兄弟包 ID」的发现来源，不依赖 `STEAM_WEB_API_KEY`；解析结果经在线校验（能解析出可下载 `file_url` 才纳入）后并入安装 ID 列表。
- 把该来源接入三处安装/预览入口：`create_install_job`、`create_catalog_install_job`、`workshop_expected_parts`。
- 为 `Left 4 SGC Beta v2.2` 增加 curated 条目（`install_ids: ["1713617501", "1713621105"]`），保证已知地图确定性安装两个包。
- 多包地图安装后新增校验：若某 `kind=map` 分组安装完成后整组没有任何 `.bsp`，在任务消息中给出可操作告警（提示可能缺少含地图的依赖包）。
- 增加面板版本标记（fix 版本），便于确认已部署修复。

## Impact
- Affected specs: l4d2-map-manager（面板安装地图）、l4d2-web-panel（面板能力）。
- Affected code: `deploy/l4d2-manager-web/app.py`（发现链、curated catalog、安装后校验、版本号）。

## ADDED Requirements

### Requirement: 从描述解析兄弟包
系统应能从 Workshop 条目的描述文本中解析出被引用的兄弟包 Workshop ID，用于多包地图安装的发现来源，且不依赖 `STEAM_WEB_API_KEY`。

#### Scenario: 描述引用第二个包
- **WHEN** 用户按 ID 安装一个 map 类型 Workshop 条目，其 `install_ids`/collection children/GetDetails children 均为空，但描述文本含 `id=<数字>` 或 `filedetails/?id=<数字>` 形式的兄弟包引用
- **THEN** 系统解析这些引用 ID，逐个在线校验（可解析出可下载 `file_url`），把校验通过的兄弟包与主包一起加入安装 ID 列表并串行安装

#### Scenario: 描述无有效引用
- **WHEN** 描述文本不含有效的兄弟包引用，或引用的 ID 无法解析为可下载项
- **THEN** 系统退回仅安装主包，行为与修复前一致，不产生误报

### Requirement: 多包地图安装后无地图告警
系统应在多包 map 安装完成后检查整组是否产出 `.bsp`，若整组无 `.bsp` 则在任务结果中给出告警提示。

#### Scenario: 整组无 bsp
- **WHEN** 一个 map 分组的所有已安装包解包后均无 `.bsp`
- **THEN** 任务成功消息中追加一条可读告警，提示该战役可能缺少含地图的依赖包、需要补装

### Requirement: SGC curated 条目
系统应为 `Left 4 SGC Beta v2.2` 提供 curated 多包条目，确保按主 ID 或名称安装时确定性地安装 `1 of 2` 与 `2 of 2` 两个包。

#### Scenario: 安装 SGC
- **WHEN** 用户按 ID `1713617501` 或名称搜索安装 SGC
- **THEN** 系统安装 `1713617501` 与 `1713621105` 两个包，切图列表出现该战役地图

## MODIFIED Requirements

### Requirement: 多包发现链
安装 ID 的发现顺序调整为：curated `install_ids` → collection children → GetDetails children（有 key 时）→ **描述兄弟包（校验后）**。任一来源产出多包即停止后续来源探测；描述来源仅在前序来源为空时作为兜底。

## ADDED Requirements（第 2 轮：VPK 目录树尾部脏字节导致误判分卷）

### Why（第 2 轮补充）
实测发现：即使多包发现正确（SGC 两包安装成功），江门新会 `3743921409` 通过面板安装仍失败。真实报错为在第 2 个包 `map_3743875149_0.51_Bata_b.vpk` 的 `--verify` 阶段抛出 `Multi-part VPK archives are not supported by this extractor`，整组 3 包安装中断。

根因：b包 `3743875149`（v1 VPK）目录树 `tree_size=239195`，但 `vpk_extract.py` 的解析循环**既不按 `tree_size` 边界停止，也不校验每条目录项规范恒为 `0xFFFF` 的 2 字节终止符**。目录树真实结束后，解析器继续把其后的二进制字节误解析成 10 条 `archive_index` 为大数（27765/23509…）、文件名乱码、`size` 达 GB 级、`term != 0xFFFF` 的“伪条目”，命中 `archive_index != 0x7FFF` 分支被判为“多分卷 VPK”而失败。实际该包 5566 条合法 inline 条目的 `maxend == filelen`，数据完整、无任何分卷文件。a包 `3743877283` 干净，解析到 `data_start` 即止，可正常安装。

### Requirement: VPK 目录树解析按边界与终止符收尾
`vpk_extract.py` 的目录树解析应在到达目录树声明边界（`header_size + tree_size`）时停止，并将每条目录项规范要求的 2 字节终止符 `0xFFFF` 作为完整性校验；对不符合规范的尾部脏字节不得误判为额外条目或分卷 VPK。

#### Scenario: 目录树尾部存在脏字节
- **WHEN** 一个单文件 inline VPK 的目录树声明边界之后残留非规范字节，且合法 inline 条目的数据范围已覆盖整个文件（无 `_NNN.vpk` 分卷）
- **THEN** 解析器在到达 `header_size + tree_size` 边界时停止读取目录项，不把边界后的字节解析为条目；`--verify` 与 `extract` 均成功，安装正常完成

#### Scenario: 真正的多分卷 VPK（保持既有行为）
- **WHEN** 一个 VPK 在目录树边界内的合法条目里含 `archive_index != 0x7FFF`（引用 `_NNN.vpk` 外部分卷）
- **THEN** 仍按既有逻辑报“不支持多分卷 VPK”，行为不变

### Requirement: 多包安装单包失败不静默丢弃告警
多包 map 分组安装中，若个别包在解析/校验阶段失败但其余包已产出可用 `.bsp`，最终任务消息应保留失败包信息（现有失败即整组失败的行为在修复解析后不再被该类脏字节触发）。

#### Scenario: 修复后重装江门新会
- **WHEN** 用户通过面板按 ID `3743921409` 安装（curated 展开为 3 包）
- **THEN** 三个包全部通过 `--verify` 与解包，切图列表出现江门新会各章节地图，任务状态为成功
