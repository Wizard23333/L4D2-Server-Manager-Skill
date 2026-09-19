# 地图管理：多 part 归组展示 + 名称可读性优化

## Summary（目标）
基于已实现的"多 part 自动关联安装"能力，优化「Map Packages」地图管理面板：
1. **归组展示**：同一张地图的多个 VPK（如 ContraZ part1/part2）不再平铺，而是归属于一个"主地图"，以可折叠主行展示，展开后看各 part 明细。
2. **名称可读性**：已下载地图以**真实地图名**展示（如 `ContraZ V0.7`），workshop id 作为副文本辅助显示。

三项产品决策（用户已确认）：
- 分组形态：**可折叠主地图行**（默认收起，点击展开各 part）
- 旧包处理：**回溯归组已装包**（对已安装但无分组信息的 workshop 地图，调 Steam children 接口重建关联并回填）
- 名称可读性：**自动拉取真实地图名**（安装时联网取 Steam title，id 作副文本）

## Current State Analysis（现状）

### 数据模型
- 每个 VPK 文件 = 一条 addon 行。包注册表 `packages.json`（`PACKAGES_FILE`）按**文件名**为 key 存储，单条记录字段见 [package_record_from_addon](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1291)：`filename / kind / source / id（本 part 的 workshop id）/ title / url / install_ids / maps / missions / status / installed_at`。
- **当前没有任何"组"关联字段**，因此前端无法归组。

### 安装链路
- 多 part 安装走 [install_catalog_bundle_job](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1897)：循环每个 part，逐个调 [register_installed_package](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1333)，每个 part **各自单独注册**，`install_ids=[当前part_id]`；title 被改写成 `标题 (1/2)`、`标题 (2/2)`（[L1940-1941](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1940)）。
- 直接输入 ID 安装走 [create_install_job](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L2036)，title 硬编码为 `"Workshop <id>"`（不可读）。
- 已有可复用：[fetch_required_children](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1392)（用 key 拉 children，返回完整 part id 列表）；[workshop_detail_result](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1521) 已能取 Steam title。

### 前端
- [PackagesPanel](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/frontend/src/App.tsx#L683) 把所有 `kind==="map"` 的 addon 平铺成 `package-row`；`title` 优先显示 `addon.title`，副文本 `addon.filename` 与 `source catalog_id`。
- 类型 `Addon`（[L31-46](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/frontend/src/App.tsx#L31)）。

## Proposed Changes（具体改动）

### 改动 1：包记录新增分组字段（app.py）
为 package 记录新增三个字段（向后兼容，缺省为空）：
- `group_id`：组的稳定标识 = 组内所有成员 workshop id 的**数值最小者**（保证无论从 part1 还是 part2 触发都归到同一组）。
- `group_title`：组的可读名称（真实地图名，去掉 `(partN)` 后缀）。
- `group_members`：组内全部 workshop id 列表（有序）。

落地点：
- **新增辅助函数 `strip_part_suffix(title)`**：去除标题尾部 `(part N)` / `（partN）` / `- part N` 等形态，得到主地图名。用正则 `re.sub(r"[\s_\-]*[\(（]?\s*part\s*\d+\s*[\)）]?\s*$", "", title, flags=re.I)`，结果为空则回退原标题。
- **新增辅助函数 `fetch_workshop_meta(workshop_id)`**：用 `STEAM_GETDETAILS_URL`+key（无 key 时回退 `STEAM_DETAILS_URL` 匿名）取 `{title, children}`，供命名与分组复用；失败返回空。
- **修改 [install_catalog_bundle_job](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1897)**：在循环前，若 `len(item_ids)>1`，计算 `group_id=min(item_ids,key=int)`、`group_title=strip_part_suffix(title)`、`group_members=item_ids`；循环内调 `register_installed_package` 时把这三个值传入。单 part（len==1）不写分组字段（保持平铺）。
- **修改 [register_installed_package](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1333)** 签名：增加 `group_id="", group_title="", group_members=None` 参数，写入包记录。
- **修改 [package_record_from_addon](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1291)** 与 [sync_package_registry](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1308)：保留已有 `group_*` 字段不被覆盖（`record.setdefault`）。

### 改动 2：真实地图名（app.py）
- **修改 [create_install_job](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L2036)**：调用前用 `fetch_workshop_meta(workshop_id)` 取真实 title，传给 `create_catalog_install_job`（取不到则回退 `Workshop <id>`）。这样直接输入 ID 安装也能得到可读名。
- 多 part bundle 已通过改动 1 的 `group_title` 取得可读名；各 part 自身 title 仍保留 `(n/total)` 供明细区分。

### 改动 3：list_addons 暴露分组字段（app.py）
- **修改 [list_addons](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L732)**：两处构造 addon dict 处，新增输出 `group_id / group_title / group_members`（从 package 记录读取，缺省空串/空列表）。

### 改动 4：回溯归组接口（app.py）
- **新增函数 `backfill_package_groups()`**：遍历包注册表，对 `source=="workshop"`、`kind=="map"`、`id` 合法、且 `group_id` 为空的记录，调 `fetch_workshop_meta(record_id)`：若 `children` 使 `fetch_required_children` 返回 `>1`，则对该组所有成员记录回填 `group_id/group_title/group_members`（`group_title` 用主 part 的 `strip_part_suffix(title)`）。返回回填组数。带节流（每次 API 调用间 `time.sleep(0.3)`）与异常吞掉，保证不阻塞。
- **新增 POST 路由 `/api/map-package/regroup`**（参照现有 `/api/job/delete` 等路由写法，在 do_POST 链中加分支）：调用 `backfill_package_groups()`，返回 `{ok, message: "已归组 N 组"}`。

### 改动 5：前端归组渲染（frontend/src/App.tsx）
- **`Addon` 类型**新增可选字段 `group_id?: string; group_title?: string; group_members?: string[]`。
- **PackagesPanel**：在 `filtered` 之后，按 `group_id`（为空则用 `catalog_id||filename` 作为单元素组）聚合成 `groups: { key, title, members: Addon[] }[]`。
  - **单成员组**：渲染为现有的 `package-row`（行为不变）。
  - **多成员组**：渲染**可折叠主行**（新增 `package-group` 容器），主行显示：
    - `group_title`（真实地图名，主标题）
    - 副文本：`workshop {group_id} · {N} 个分卷` + 真实地图名旁的 id
    - 聚合大小（成员 size 求和）、聚合状态 Pill（全 enabled→enabled；含 disabled→mixed/disabled；含 remote→缺卷提示）
    - 一个展开/收起按钮（用现有 `useState` 局部展开集合管理，参照 JobsPanel 折叠交互）
  - 展开后逐行渲染各 part（复用现有 `package-row` 的操作按钮：Enable/Disable、Reinstall、Export、Delete、Manifest 勾选等，**操作粒度保持在单 part**，不改后端单文件操作语义）。
- **命名展示**：主行标题用 `group_title`；单包行标题改为"优先 `addon.title` 去后缀、其次 filename"，并把 `workshop {catalog_id}` 作为副文本（id 作可读性辅助，符合需求 2）。
- **触发回溯**：面板头部加一个次级按钮「重建分组关联」，调 `/api/map-package/regroup` 后 `loadState` 刷新（让用户对历史已装包一键归组）。

### 改动 6：样式（frontend/src/styles.css）
- 新增 `.package-group`、`.package-group-head`、展开/收起箭头、`.package-group .package-row`（缩进/左边线）等少量样式，沿用现有配色（启用绿、禁用黄左边线、问题红边）。复用既有 `.package-row` 间距规范。

## Assumptions & Decisions（假设与决策）
- **分组稳定键**用 `min(member_ids)`，保证从任一 part 安装/回溯都归同一组；组标题用主 part 标题去 `(partN)` 后缀。
- **操作粒度**保持单 VPK（Enable/Disable/Delete/Reinstall 仍按文件），不引入"整组操作"，避免改动后端文件操作语义、控制复杂度。（如后续需要"整组启停"可再迭代。）
- **回溯归组**为显式按钮触发（非自动后台扫描），避免每次 loadState 都打 Steam API；符合"最小副作用"。
- 无 Steam key 时：`fetch_required_children` 返回 `[]`，分组功能自然降级为平铺，命名回退匿名 title 或 `Workshop <id>`，不报错。
- 构建产物：前端改动需 `npm run build` 重新生成 `static/assets/*.js`，更新 `static/index.html` 引用（沿用既有部署流程，含 static-backup 时间戳备份）。

## Verification（验证步骤）
1. **后端单测**（服务器 /tmp，带 key）：
   - `strip_part_suffix("ContraZ V0.7(part1)") == "ContraZ V0.7"`；对无后缀标题原样返回。
   - `fetch_workshop_meta("1987326534")` 返回真实 title 与 children。
   - 构造含 part1/part2 的 packages，调 `backfill_package_groups()` 后两条记录 `group_id` 相同、`group_title` 可读。
2. **list_addons** 输出含 `group_id/group_title/group_members`，本地与服务器 `py_compile` 通过。
3. **前端**：`npm run build` 成功；本地预览检查：
   - 多 part 地图折叠为一主行，展开见各 part；单包仍平铺。
   - 标题显示真实地图名，id 作副文本。
   - 「重建分组关联」按钮可把历史已装的 ContraZ/3220375446 两组归好。
4. **部署**：备份现有 app.py 与 static → 替换 → 权限 → 重启服务；经 SSH 隧道浏览器复核（Ctrl+F5 硬刷新）。
5. 端到端：面板用任一 part ID 安装 → 自动下载所有 part → 地图管理中以单一主地图行（真实名）展示，展开见全部分卷。

## 不做项
- 不引入"整组一键启停/删除"（保持单 part 操作，控制范围）。
- 不改动 mods（非 map）展示。
- 不做后台自动定时归组（仅手动按钮触发）。
