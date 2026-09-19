# 代理下载（浏览器本机中继安装）实现计划

## Summary

为 Steam Workshop 地图/Mod 安装新增一个**代理下载**选项：默认仍走服务器直连 Steam CDN 下载；当服务器访问 Steam 异常或下载不稳定时，管理面板访问者可勾选"代理下载"，由**访问者本机**完成下载，再回传到服务器复用已有上传安装管线落地。

采用**半自动方案**（用户确认）：
1. 后端解析 Workshop 直链与建议文件名（小 API，服务器只访问 `api.steampowered.com`，不下大文件）；
2. 浏览器**原生下载**该直链到访问者本地（走本机网络，不受 CORS 限制，可靠绕开服务器 Steam CDN 瓶颈）；
3. 访问者把下载好的 vpk 通过现有 `/api/upload` 管线一键上传安装（VPK 签名/结构校验 + `import-vpk` 落地 + 注册表登记）。

增补功能（用户要求）：代理下载入口同时提供**本地 addons 目录直传**——访问者可直接选取本机已存在的、符合命名要求的 vpk 文件上传安装，省去重复下载。本质是复用同一个文件选择→上传流程，UI 上引导用户从本机 `addons` 目录挑选。

范围：**仅 Workshop**（GameMaps 不纳入本期）。

## Current State Analysis

### 安装下载链路（服务器直连）
- 路由 [app.py L5011-5026](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L5011-L5026)：`/api/workshop/install`、`/api/catalog/install` → `create_install_job` / `create_catalog_install_job`。
- [create_catalog_install_job L2211-2262](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L2211-L2262)：解析合集子项 → 起线程 `install_catalog_bundle_job` → `l4d2-webctl install-workshop`（**在服务器上**用 `file_url` 下 CDN 大文件）。
- [l4d2-webctl install_workshop L788+](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/l4d2-webctl#L788-L827)：`fetch_workshop_details` 拿 `file_url`/`file_size`/`title` → `download_file`（Range 续传）→ `verify_downloaded_vpk` → 落地 `addons`。

### 已有的"上传→安装"管线（可直接复用）
- 路由 [app.py L4990-4992](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L4990-L4992)：`/api/upload` → `handle_upload_request` → `create_upload_job`。
- [create_upload_job L3177-3212](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L3177-L3212)：multipart 暂存到 `UPLOADS_DIR` → `assert_vpk_signature` 签名校验 → `create_transfer_job`。
- [run_transfer_job L3123-3174](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L3123-L3174)：`l4d2-webctl import-vpk` → 校验 + 落地 + `register_installed_package` 登记。`kind`（map/mod）与 `final_filename` 已支持，最大 2GB（`MAX_UPLOAD_BYTES`）。
- 前端通用上传函数 [App.tsx upload() L1024-1037](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/frontend/src/App.tsx#L1024-L1037)：`FormData` + `/api/upload`，已是成熟模式。

### Steam 直链解析（小 API，服务器侧已能用）
- [workshop_detail_result L1649-1693](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L1649-L1693) 与 `fetch_workshop_details`（webctl）/`fetch_workshop_meta`：通过 `api.steampowered.com` GetPublishedFileDetails 返回 `file_url`、`file_size`、`title`、合集 `children`。这些是轻量 API 调用，即使大文件 CDN 不稳定也通常能成功。

### 关键技术约束（已用 WebSearch + 既有实现确认）
- Steam UGC 文件 CDN（`*.steamusercontent.com` / akamai）响应**不带 `Access-Control-Allow-Origin`**。浏览器 JS `fetch(file_url)` 读取响应体会被 CORS 拦截 → **纯 JS 自动中继不可行**。
- 浏览器**原生下载**（`window.open` / `<a href download>`）不受 CORS 限制，走访问者本机网络 → 这是可靠路径。
- 因此采用"后端给直链 → 浏览器原生下载 → 用户回传上传"的半自动闭环。

### InstallPanel 现状
- [InstallPanel L547-657](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/frontend/src/App.tsx#L547-L657)：Workshop ID 安装框 + 搜索结果列表，每个结果有"Install"按钮（服务器直装）。上一轮已加 `submitting` 遮罩。

## Proposed Changes

### 1. 后端：新增直链解析接口（app.py）

**新增函数 `resolve_workshop_download(workshop_id)`**（放在 `workshop_detail_result` 附近，约 L1693 后）：
- 校验 `WORKSHOP_ID_RE`。
- 复用 `fetch_workshop_details`（已存在于 webctl，但 app.py 用的是 `http_json(STEAM_DETAILS_URL,...)`，见 `workshop_detail_result`）调 `STEAM_DETAILS_URL` 取 `file_url`、`file_size`、`title`。
- 计算**建议文件名**：复用 webctl 同款命名规则 `{kind}_{workshop_id}_{safe_title}.vpk`（在 app.py 内用 `safe_title` 等价逻辑；若无则内联一个与 webctl 一致的 `re.sub(r"[^A-Za-z0-9_.-]+","_",...)[:80]`）。
- 返回 `{"ok": True, "workshop_id", "kind", "title", "file_url", "file_size", "suggested_filename"}`；失败返回 `{"ok": False, "message"}`（如无 `file_url`，提示该项可能是合集或被限制）。
- 对合集：用 `fetch_collection_children` 展开，对每个子项分别解析，返回 `items: [{workshop_id, file_url, suggested_filename, file_size, title}]`，让前端逐个原生下载。

**新增 GET 路由** `/api/workshop/resolve`（[do_GET](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/app.py#L4932-L4941) 内 `/api/catalog/search` 附近）：
- 入参 `workshop_id`、`kind`（默认 map）。
- 调 `resolve_workshop_download`，`send_json`。
- 需在 `do_GET` 已有鉴权保护下（该方法在 `authenticated()` 之后才到这些分支，符合现状）。

> 说明：直链下载与上传安装均复用现有 `/api/upload` 管线，**无需新增上传路由**；`import-vpk` 已做 VPK 校验、落地、登记，满足"安装前必须 verify"硬约束。`final_filename` 由前端用 `suggested_filename` 透传，后端 `safe_upload_final_name` 兜底。

### 2. 前端：InstallPanel 增加"代理下载"入口（App.tsx）

在 [InstallPanel](file:///d:/workspace/L4D2-Server-Manager-Skill/deploy/l4d2-manager-web/frontend/src/App.tsx#L547-L657) 内：

**a. Workshop ID 安装行增加模式选择**
- 在现有 `installWorkshop`（服务器直装）旁，增加一个 **"Proxy download"** 按钮（次要样式）。
- 点击后调 `GET /api/workshop/resolve?workshop_id=&kind=`，进入"代理下载向导"状态 `proxyResolve`。

**b. 搜索结果项**
- 每个可安装结果在"Install"（服务器直装，保持默认）旁加一个 **"Proxy"** 小按钮，行为同上（用该项 id+kind 解析）。

**c. 代理下载向导（新增轻量内联区块 / 复用 `busy-overlay` 风格的卡片）**
解析成功后展示一个 `ProxyDownloadCard`（新增组件或内联）：
- 列出 1..N 个待下载项（合集多 part 全部列出），每项显示标题、建议文件名、大小（用已有 `formatBytes`）。
- 每项一个 **"① 下载到本机"** 按钮：用 `window.open(file_url, "_blank")` 或动态 `<a download>` 触发**浏览器原生下载**（不受 CORS 限制）。
- 每项一个 **"② 选择文件并安装"** 文件选择（复用 `FileField` 模式 + `accept=".vpk"`）：选中后调用现有 `/api/upload`（`FormData` 带 `file`、`kind`），即上传安装。上传期间复用 `submitting` 遮罩防重复点击。
- 顶部提示文案：引导"先点①让本机下载，下载完成后点②选取该 vpk 上传安装"。

**d. 本地 addons 目录直传（增补功能）**
- 在向导卡片或 Workshop 行提供一个独立的 **"从本机 addons 选择已有文件直传"** 文件选择（`accept=".vpk"`，`multiple` 可选）：
  - 用户直接从本机 `left4dead2/addons` 选 vpk → 直接 `/api/upload` 上传安装，跳过下载步骤。
  - 文案说明：若本机已有符合要求的 vpk 则直接选取上传，否则用①②流程现下载。
- 实现上与 ②共用同一个上传函数；仅 UI 文案/入口不同。

**类型/状态**：InstallPanel 内新增 `proxyResolve` 状态（解析结果）与 `submitting`（已存在）。新增 `resolveProxy(workshopId, kind)`、`installLocalFile(file, kind, finalName?)` 两个 async 函数，均 `try/finally` 管理遮罩并 `loadState` 刷新。

### 3. 样式（styles.css）
- 复用现有 `.busy-overlay/.busy-card/.tool-card/.actions` 等既有类与品牌变量，**尽量不新增大量 CSS**。
- 如需，新增 `.proxy-card` 轻量样式（列表项排版），沿用 `--surface/--line/--r-md/--font-mono` 等变量，保持深松绿浅色主题一致。

## Assumptions & Decisions

1. **半自动方案**（用户选定）：后端只解析直链；下载由浏览器原生完成；安装走现有上传管线。不尝试 JS 自动 fetch 中继（CORS 不可行）。
2. **仅 Workshop**（用户选定）：`/api/workshop/resolve` 只处理 Workshop；GameMaps 不纳入。
3. **复用上传管线**：不新增"暂存→安装"后端逻辑，直接用 `/api/upload`（`import-vpk`，含 VPK verify、2GB 上限、注册表登记），满足安全/校验硬约束。
4. **本地目录直传**为②上传流程的 UI 变体，不需额外后端。
5. **服务器直装保持默认**，代理为可选项，零回退风险。
6. **合集多 part**：解析展开为多项，前端逐项①②，用户自行完成每个 part（与现有多 part 心智一致）。
7. **凭据安全**：`file_url` 含 Steam 临时签名，仅在面板内展示给已登录访问者，不落日志；遵循 AGENTS.md 不暴露密钥要求（file_url 非长期密钥，可展示）。

## Verification

1. **本地语法**：`python -m py_compile app.py`；`npm run build`（tsc + vite）通过。
2. **后端接口**：部署后 `curl`（带 session cookie）`/api/workshop/resolve?workshop_id=<已知ID>&kind=map`，确认返回 `file_url`/`suggested_filename`/`file_size`；合集 ID 返回多项。
3. **前端功能**（浏览器，Ctrl+F5 硬刷新）：
   - Workshop 行点 "Proxy download" → 出现向导卡片，列出待下载项。
   - 点①触发浏览器原生下载（确认下载到本机、走本机网络）。
   - 点②选取下载好的 vpk → 上传安装成功，安装后出现在 Map Packages 且 `package_status` 正确。
   - 本地 addons 直传：选本机已有 vpk → 上传安装成功。
   - 上传期间遮罩生效，无法重复点击。
   - 服务器直装路径不受影响（回归）。
4. **部署**：`app.py` 备份→scp→替换→`chown l4d2web:l4d2web`→`restart`→`systemctl is-active`=active，日志无报错；前端 `static` 备份→替换→`chown`→restart。

## Out of Scope
- GameMaps 代理下载。
- JS 全自动 fetch 中继（CORS 限制，已排除）。
- 服务器端代理转发（仍是服务器出网，不解决服务器访问异常问题，故不做）。
