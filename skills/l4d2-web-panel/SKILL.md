---
name: "l4d2-web-panel"
description: "L4D2 Web 管理面板的部署与运维。当需要部署或更新仓库 deploy/l4d2-manager-web/ 下的轻量浏览器管理面板（查看房间状态、切换默认地图、搜索安装地图、管理 VPK/插件）、了解面板功能边界与安全白名单（sudoers/l4d2-webctl）、或运行面板验证脚本时调用。它是可选附加能力，不是 SSH/RCON/脚本流程的前置条件。"
---

# L4D2 Web 管理面板

Web 管理面板是部署在服务器上的轻量浏览器界面，适合日常查看房间状态、切换默认地图、搜索安装三方地图和管理 VPK。它是本套 skill 的**可选附加能力**，不是使用 SSH、RCON 和脚本流程的前置条件；不需要网页时，仍可完全按 `l4d2-server-setup` / `l4d2-map-manager` / `l4d2-plugin-manager` 的命令行流程管理服务器。

> 安全规范：登录配置只保存在服务器 `/etc/l4d2-manager-web.env`；不要把 Web 登录密码、RCON 密码、GSLT、Steam token、SSH 私钥、代理订阅写入公开文档、Issue、提交说明或聊天记录。

---

## 1. 部署包结构

部署包位于仓库的 `deploy/l4d2-manager-web/`，核心文件包括：
- `app.py`：Web/API 服务，默认监听 `8080/tcp`。
- `l4d2-webctl`：受限 root helper，只暴露经过校验的管理子命令。
- `vpk_extract.py`：地图类 VPK 的受限提取工具，只提取允许的游戏资源目录。
- `l4d2-manager-web.service`：systemd unit，用于常驻运行 Web 服务。
- `l4d2-manager-web.sudoers`：sudoers 白名单，只允许 Web 用户调用指定 helper 和重启指定房间服务。
- `install.sh`：把上述文件安装到服务器对应位置的部署入口。

## 2. 面板功能边界

当前面板提供的功能边界：
- 查看 Room 1 / Room 2 状态、端口监听和默认地图。
- 重启指定房间。
- 按"战役 -> 子地图"二级选择默认地图，并可选择只保存或保存后重启房间。
- `Search & Install` 以 Steam Workshop 搜索为主，GameMaps 作为受控兜底来源；也保留手动输入 Workshop ID 的安装入口。
- Workshop 安装使用 `install-workshop <map|mod> <workshop_id>`；GameMaps 只允许 `install-gamemaps-map <numeric_id>`，不支持任意 URL 下载。
- 安装任务在后台执行，页面显示进度条、当前阶段和分包进度；job 状态持久化到 `/var/lib/l4d2-manager-web/jobs/`，刷新页面后仍可查看未完成或历史任务，并可提前取消仍在排队或运行中的任务。
- 区分 Map Packages 与 Mod Management，避免把含地图的 VPK 当作普通 Mod 管理；地图包支持 `Reinstall`、普通删除和彻底删除。
- Transfer 区域推荐使用轻量 JSON Manifest 迁移 Workshop 地图和 Mod 的 ID 与来源记录；导入后由用户手动重新下载。大文件 `.vpk` / 迁移 ZIP 仍保留为离线迁移方式。
- 启用/禁用已有 `.vpk`，仅在 `addons/` 与 `addons_disabled/` 之间移动文件，不提供删除和任意 shell 输入。
- 地图列表会识别 loose `.bsp`，也会索引启用 VPK 内的 `maps/*.bsp` 与 `missions/*.txt`，并按战役分组展示；mission parser 支持非固定顶层 key，可识别 Glubtastic 4/5 这类自定义 mission。
- Web 面板会维护地图包来源记录，例如 `/var/lib/l4d2-manager-web/packages.json`，用于展示来源链接、重装入口和普通删除后的恢复入口。
- GameMaps 可能被 Cloudflare 阻断，页面应显示失败 job；`Run To The Hills` 已验证可通过 Workshop `2232584588` 安装，章节地图为 `rh_map01` 到 `rh_map05`。

> 面板的"服务器插件"栏对 SourceMod `.smx` 的动态扫描与启停逻辑，见 `l4d2-plugin-manager`。

## 3. 部署步骤

```bash
# 本地仓库中执行，将部署包同步到服务器临时目录
ssh myubuntu "mkdir -p /tmp/l4d2-manager-web"
scp deploy/l4d2-manager-web/* myubuntu:/tmp/l4d2-manager-web/

# 服务器上安装/更新 Web 面板
ssh myubuntu "cd /tmp/l4d2-manager-web && sudo bash install.sh"
```

安装脚本会：
- 创建或复用系统用户 `l4d2web`。
- 安装 Web 程序到 `/opt/l4d2-manager-web/`。
- 安装 helper 到 `/usr/local/bin/l4d2-webctl`。
- 安装 systemd unit 到 `/etc/systemd/system/l4d2-manager-web.service`。
- 安装 sudoers 白名单到 `/etc/sudoers.d/l4d2-manager-web`。
- 首次部署时生成 `/etc/l4d2-manager-web.env`，后续部署保留已有登录配置。
- 下载默认直连；只有显式设置非空的 `L4D2_DOWNLOAD_PROXY` 时才使用 HTTP/HTTPS 代理。
- `daemon-reload` 后启用并重启 `l4d2-manager-web.service`。

如服务器确实运行了本地代理，可显式启用并重启面板：

```bash
sudo sed -i 's|^L4D2_DOWNLOAD_PROXY=.*|L4D2_DOWNLOAD_PROXY=http://127.0.0.1:7890|' /etc/l4d2-manager-web.env
sudo systemctl restart l4d2-manager-web
```

不使用代理时保持 `L4D2_DOWNLOAD_PROXY=` 即可。安装脚本不会覆盖已有的非空配置。

## 4. 安全注意事项

- 面板浏览器入口使用页面内登录表单和 session cookie；脚本仍兼容 Basic Authorization。登录配置保存在服务器 `/etc/l4d2-manager-web.env`；文档、Issue、提交说明和聊天记录中不要记录真实密码。
- 访问面板需要同时放行服务器本机防火墙和云安全组的 `8080/tcp`。
- 所有需要 root 权限的操作必须经过 `/usr/local/bin/l4d2-webctl`，不要让 Web 服务执行任意 shell。
- sudoers 只白名单以下能力：重启 `l4d2` / `l4d2_2`、`set-default-map`、`install-workshop`、`install-gamemaps-map`、`set-addon-state`、`delete-map-package`、`cleanup-job-temp`、`import-vpk`、`import-export-zip`。
- 普通删除只删除本地地图包和已提取文件，但保留来源记录以便重装；彻底删除会同时移除来源记录，后续需要重新搜索或重新输入 Workshop ID。
- GameMaps 入口只接受数字 details id，并从 `https://www.gamemaps.com/details/<id>` 派生下载；不要增加任意 URL 输入框。
- 不要把 RCON 密码、GSLT、Steam token、SSH 私钥、代理订阅或 Web 登录密码写入公开文档。

## 5. 验证

常用检查命令：
```bash
sudo systemctl status l4d2-manager-web --no-pager
sudo systemctl restart l4d2-manager-web
sudo ss -H -ltnp 'sport = :8080'
sudo test -f /etc/l4d2-manager-web.env
```

部署后验证：
```bash
sudo python3 /tmp/l4d2-manager-web/verify_api.py
sudo python3 /tmp/l4d2-manager-web/verify_home.py
sudo python3 /tmp/l4d2-manager-web/verify_phase3.py
```

安装地图前后确认不会自动重启房间：
```bash
sudo systemctl show l4d2 l4d2_2 -p ExecMainStartTimestamp --no-pager
```

---

## 6. 多包地图安装与 `STEAM_WEB_API_KEY`

### 问题现象
通过面板按 Workshop ID 安装某些「多包地图」时，只装上了其中一个包（往往是仅含 `materials/`、`models/` 的资源包，没有 `.bsp`），导致地图不出现在切图列表里。典型例子：`Left 4 SGC Beta v2.2 (1 of 2)`（ID `1713617501`）只含资源，真正含地图的 `2 of 2`（ID `1713621105`）需要一并安装。

### 根因
面板的多包发现链依次为：curated `install_ids` → collection children → **GetDetails `children`（需要 `STEAM_WEB_API_KEY`）** → 描述文本兄弟包解析（兜底）。

部分多包地图既不是 collection，也没有把兄弟包声明成 `children`，而是只在 **Workshop 描述文本**里用 `id=<数字>` 的形式提到第二个包（例如 `Part 2 NEEDED TOO ... id=1713621105`）。当服务器 **缺少 `STEAM_WEB_API_KEY`** 时，`IPublishedFileService/GetDetails` 无法返回 `children`，这一层发现直接失效，面板就只能装到用户输入的那个单包。

### 处理方式（两条互补）
1. **配置 `STEAM_WEB_API_KEY`（推荐，通用增强）**
   - 在 https://steamcommunity.com/dev/apikey 用 Steam 账号申请（域名随便填如 `localhost`），得到一串 32 位 key。
   - 写入面板环境文件并重启服务（key 属于机密，命令里用占位符，不要写入公开文档 / 提交记录 / 聊天）：
     ```bash
     echo 'STEAM_WEB_API_KEY=YOUR_STEAM_WEB_API_KEY' | sudo tee -a /etc/l4d2-manager-web.env >/dev/null
     sudo chmod 0600 /etc/l4d2-manager-web.env
     sudo systemctl restart l4d2-manager-web
     ```
   - 验证进程已加载（应输出 `1`）：
     ```bash
     pid=$(systemctl show -p MainPID --value l4d2-manager-web)
     sudo cat /proc/$pid/environ | tr '\0' '\n' | grep -c '^STEAM_WEB_API_KEY='
     ```
   - 作用：让通过 GetDetails `children` 声明兄弟包的多包地图也能被自动发现。它是**可选增强，不是面板运行的前置条件**。

2. **不依赖 key 的兜底能力（面板自带，`L4D2Manager/0.2` 起）**
   - `fetch_description_sibling_ids()`：从 Workshop 描述文本解析 `id=` / `filedetails/?id=` 引用的兄弟包，逐个在线校验能否下载后并入安装列表，**不需要 key**。
   - 已知多包地图应登记 curated `install_ids`（如 SGC = `["1713617501","1713621105"]`），获得确定性安装，不受网络/描述格式波动影响。
   - 多包 map 安装完成后若整组仍无任何 `.bsp`，任务结果会给出「可能缺少含地图的依赖包，请补装」的告警。

### 排查提示
- 装完发现切图列表没有该地图时，先确认是否是「资源包 + 地图包」结构：
  ```bash
  # 查看某 VPK 内是否含 maps/*.bsp
  python3 /opt/l4d2-manager-web/vpk_extract.py --list /opt/l4d2/left4dead2/addons/<file>.vpk 2>/dev/null | grep -i '\.bsp$' || echo "此包无 bsp（可能是资源包）"
  ```
- 若确属多包但只装了一个，优先补配 `STEAM_WEB_API_KEY`，或为该地图在 `app.py` 的 `KNOWN_CATALOG_ITEMS` 补一条带完整 `install_ids` 的 curated 条目。
