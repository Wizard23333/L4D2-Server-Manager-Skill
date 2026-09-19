---
name: "l4d2-backup-migrate"
description: "L4D2 服务器完整状态备份与跨机迁移。当服务器租期到期、需要更换机器，或想把一台 L4D2 服务器的完整运行状态（启动脚本、server*.cfg、systemd unit、SourceMod 插件栈与禁用态、自写 .sp 源码、管理员白名单、/etc/hosts CDN 与 /etc/gai.conf 网络加速、Web 面板 env/packages.json）保存到本地，并在新服务器上还原部署时调用。地图等大体积 VPK 只保留 Workshop ID 到新机重新下载。不负责常规搭建（见 l4d2-server-setup）、日常地图安装/切换（见 l4d2-map-manager）、插件日常管理（见 l4d2-plugin-manager）、Web 面板部署（见 l4d2-web-panel）。"
---

# L4D2 服务器完整状态备份与迁移

本 skill 覆盖「旧服务器到期前的完整状态备份 -> 拉取到本地 -> 新服务器还原部署」全链路，是横跨 setup / map / plugin / web-panel 四个领域的整机迁移入口。

边界说明：
- 新机的系统接入、SSH、防火墙、SteamCMD 装 L4D2 本体见 `l4d2-server-setup`（迁移的**前置条件**）。
- 地图的日常安装/切换见 `l4d2-map-manager`；本 skill 只负责「保留地图 ID 清单 + 新机批量重装」。
- 插件日常启停、自写 SourcePawn 编译细节见 `l4d2-plugin-manager`；本 skill 复用其 `spcomp64` 重编译思路。
- Web 面板部署见 `l4d2-web-panel`；本 skill 只迁移其 env 与 `packages.json` 状态。

> 安全规范：备份产物含 `rcon_password`、GSLT、Web 登录 env、SteamID 等敏感值。这些只允许保存在你本地的私有路径，**不要**写入仓库、Issue、提交说明或聊天记录。本文档命令中的密码/token 一律用 `YOUR_RCON_PASSWORD`、`YOUR_GSLT_TOKEN` 等占位符。还原后改变服务器状态前优先做只读健康检查。

---

## 1. 迁移设计原则

把服务器状态分成两类，区别对待：

- **A 类 — 完整迁移（小体积，原样还原）**：配置、脚本、systemd、插件栈、白名单、网络加速、面板状态。这些是你长期积累、无法靠"重新下载"自动恢复的状态，必须打包带走。
- **B 类 — 仅保留 ID（大体积，新机重下）**：地图 VPK 与已提取的 `.bsp` 资源。它们体积大且可由 Workshop ID 重新获取，因此只保留 ID/来源清单，新机用 `l4d2-add-map` 或 Web 面板按 ID 重装。

核心取舍：**插件信息追求完整迁移，地图只迁移 ID**。

---

## 2. 迁移清单（Migration Manifest）

### A 类 — 完整迁移

| # | 状态项 | 服务器路径 | 说明 |
| --- | --- | --- | --- |
| A1 | 启动脚本 | `/opt/l4d2/start_l4d2.sh`、`/opt/l4d2/start_l4d2_2.sh` | 含 `+map` / `+hostport` / `+sv_hibernate_when_empty` 等参数；可能含 GSLT/rcon，属敏感文件 |
| A2 | 房间配置 | `/opt/l4d2/left4dead2/cfg/server.cfg`、`server_2.cfg` | 含 `sv_steamgroup`、可见性参数、`rcon_password`，属敏感文件 |
| A3 | systemd unit | `/etc/systemd/system/l4d2.service`、`l4d2_2.service` | 新机需 `daemon-reload` 后 enable |
| A4 | SourceMod 插件栈 | `addons/sourcemod/plugins/`（启用）、`addons/sourcemod/plugins/disabled/`（禁用态）、`addons/sourcemod/configs/`、`cfg/sourcemod/` | **禁用态本身也是状态**，必须连 `disabled/` 一起迁移 |
| A5 | 自写插件源码 | 仓库 `deploy/l4d2-manager-web/plugins/*.sp`（如 `infected_counter.sp`） | 随仓库走，新机用 `spcomp64` 重新编译，**不直接搬 `.smx` 二进制** |
| A6 | 插件类 VPK（含禁用态） | `addons/left4bots2.vpk`、`left4lib.vpk`、`admin_system.vpk`，以及 `addons_disabled/` 下的禁用 VPK | 体积相对小，直接迁移；**禁用态目录 `addons_disabled/` 也要带走**（与 A4 同理，禁用态本身是状态）；同时记录 Workshop ID（`2279814689` / `2634208272` / `213591107`）作兜底 |
| A7 | 管理员白名单 | `ems/left4bots/cfg/admins.txt`、`ems/admin system/admins.txt` | 含 SteamID，属敏感文件 |
| A8 | 网络加速 | `/etc/hosts` 的 `L4D2-STEAM-CDN` 块、`/etc/gai.conf` 的 `precedence ::ffff:0:0/96 100` 行 | 国内访问 Steam 的关键，新机要重建 |
| A9 | Web 面板状态（如启用） | `/etc/l4d2-manager-web.env`（敏感）、`/var/lib/l4d2-manager-web/packages.json` | env 含登录配置；`packages.json` 是地图来源/ID 记录，是 B 类重下的依据 |

> 路径基于当前服务器快照（安装目录 `/opt/l4d2`，两房间共享 `/opt/l4d2/left4dead2/`，非 root 用户 `steam`）。实际迁移前先 `ssh myubuntu "ls <路径>"` 确认存在性，缺失项跳过即可。

### B 类 — 仅保留 ID，新机重新下载

| # | 状态项 | 处理方式 |
| --- | --- | --- |
| B1 | 地图 VPK / 已提取 `.bsp` | 只导出 Workshop ID + 来源记录（优先取 A9 的 `packages.json`），新机用 `l4d2-add-map <ID>` 或 Web 面板按 ID 重装 |
| B2 | SteamCMD workshop 缓存 `/home/steam/Steam/steamapps/workshop/content/550/` | 不迁移（可由 ID 重新下载，纯缓存） |

> 不纳入迁移、按新机重建的项：Steam 代理（Clash/mihomo + Proxychains，`/tmp/proxychains_l4d2.conf`）属临时态且订阅敏感，新机按 `l4d2-server-setup` 重建；`l4d2-add-map` helper（`/usr/local/bin/l4d2-add-map`）随新机搭建/Web 面板安装恢复，是 §4 步骤7 重下地图的前置。MetaMod:Source + SourceMod 框架本体由 §4 步骤3 的前置（按 `l4d2-plugin-manager` 重装框架）覆盖。

---

## 3. 备份流程（在旧服务器执行 + 拉取到本地）

目标：在本地得到一个结构化备份目录，A 类文件完整、B 类只剩 ID 清单。

### 本地备份目录结构

```
l4d2-migrate-backup/
  scripts/        # A1 start_l4d2*.sh
  cfg/            # A2 server*.cfg
  systemd/        # A3 *.service
  sourcemod/      # A4 plugins/ plugins/disabled/ configs/ + cfg/sourcemod/（打进 sourcemod.tar.gz）
  plugin-src/     # A5 *.sp（来自本地仓库 deploy/.../plugins/）
  addons-vpk/     # A6 插件类 vpk（启用）
  addons-vpk-disabled/ # A6 插件类 vpk（禁用态）
  ems/            # A7 admins.txt
  network/        # A8 hosts 片段 + gai.conf 片段
  webpanel/       # A9 env + packages.json
  maps-manifest/  # B1 地图 ID 清单
  RESTORE-INDEX.md# 还原说明索引（手写/复制本节要点）
```

### 步骤 1：在服务器上把 A 类状态归集到一个临时目录并打包

PowerShell→ssh→bash 链路有引号/括号转义陷阱（`$(date)`、here-doc、`>>>` 等会被本地 PowerShell 解析）。**时间戳在 PowerShell 侧先生成**，把整段远程逻辑用 base64 传过去执行，规避所有转义问题：

```powershell
# 本地 PowerShell
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$remote = @"
set -e
B=/tmp/l4d2-mig-$ts
mkdir -p `$B/scripts `$B/cfg `$B/systemd `$B/sourcemod `$B/addons-vpk `$B/addons-vpk-disabled `$B/ems `$B/network `$B/webpanel `$B/maps-manifest
# A1 启动脚本
sudo cp /opt/l4d2/start_l4d2.sh /opt/l4d2/start_l4d2_2.sh `$B/scripts/ 2>/dev/null || true
# A2 房间配置
sudo cp /opt/l4d2/left4dead2/cfg/server.cfg /opt/l4d2/left4dead2/cfg/server_2.cfg `$B/cfg/ 2>/dev/null || true
# A3 systemd unit
sudo cp /etc/systemd/system/l4d2.service /etc/systemd/system/l4d2_2.service `$B/systemd/ 2>/dev/null || true
# A4 SourceMod 插件栈（含 disabled 态 + configs + cfg/sourcemod）
sudo tar -czf `$B/sourcemod/sourcemod.tar.gz -C /opt/l4d2/left4dead2 addons/sourcemod/plugins addons/sourcemod/configs cfg/sourcemod 2>/dev/null || true
# A6 插件类 VPK（含禁用态目录）
sudo cp /opt/l4d2/left4dead2/addons/left4bots2.vpk /opt/l4d2/left4dead2/addons/left4lib.vpk '/opt/l4d2/left4dead2/addons/admin_system.vpk' `$B/addons-vpk/ 2>/dev/null || true
sudo cp /opt/l4d2/left4dead2/addons_disabled/*.vpk `$B/addons-vpk-disabled/ 2>/dev/null || true
# A7 管理员白名单
sudo cp /opt/l4d2/left4dead2/ems/left4bots/cfg/admins.txt `$B/ems/l4b2-admins.txt 2>/dev/null || true
sudo cp '/opt/l4d2/left4dead2/ems/admin system/admins.txt' `$B/ems/adminsystem-admins.txt 2>/dev/null || true
# A8 网络加速（只摘相关片段）
sudo sed -n '/# L4D2-STEAM-CDN-BEGIN/,/# L4D2-STEAM-CDN-END/p' /etc/hosts > `$B/network/hosts-cdn-block.txt 2>/dev/null || true
grep '::ffff:0:0/96' /etc/gai.conf > `$B/network/gai.conf.line 2>/dev/null || true
# A9 Web 面板状态（如启用）
sudo cp /etc/l4d2-manager-web.env `$B/webpanel/ 2>/dev/null || true
sudo cp /var/lib/l4d2-manager-web/packages.json `$B/webpanel/ 2>/dev/null || true
# B1 地图 ID 清单：优先 packages.json；兜底列出已装 .bsp 名称
sudo cp /var/lib/l4d2-manager-web/packages.json `$B/maps-manifest/packages.json 2>/dev/null || true
ls /opt/l4d2/left4dead2/maps/*.bsp 2>/dev/null | xargs -n1 basename 2>/dev/null | sed 's/\.bsp//' > `$B/maps-manifest/installed-bsp.txt || true
ls /opt/l4d2/left4dead2/addons/*.vpk 2>/dev/null | xargs -n1 basename 2>/dev/null > `$B/maps-manifest/installed-vpk.txt || true
# 统一归属当前用户并打总包
sudo chown -R `$USER:`$USER `$B
tar -czf /tmp/l4d2-mig-$ts.tar.gz -C /tmp l4d2-mig-$ts
echo PACKED:/tmp/l4d2-mig-$ts.tar.gz
"@
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remote))
ssh myubuntu "echo $b64 | base64 -d | bash"
```

> 说明：PowerShell here-string 中 `` `$ `` 表示传给远程的字面 `$`（远程 bash 变量），不带反引号的 `$ts` 在本地展开为时间戳。`admin system` 目录名含空格，必须整体加引号。所有 `cp` 都带 `|| true`，缺失文件不会中断。

### 步骤 2：把总包拉到本地

```powershell
# 仍在本地 PowerShell（用上一步打印的 PACKED 路径）
scp myubuntu:/tmp/l4d2-mig-$ts.tar.gz .
# 解压到本地备份目录后，A5 自写插件源码直接来自本仓库，无需从服务器取：
#   deploy/l4d2-manager-web/plugins/*.sp 已随仓库版本管理
```

### 步骤 3：核对地图 ID 清单（B 类）

- 首选 `webpanel/packages.json`：含每张地图的 Workshop ID 与来源链接，是最完整的重下依据。
- 若未启用 Web 面板，则用 `maps-manifest/installed-vpk.txt` / `installed-bsp.txt` 人工回忆对应 Workshop ID。常用入口可参考 `l4d2-map-manager` 的已验证地图清单。

---

## 4. 新服务器还原流程（按依赖顺序）

> 前置：新服务器已按 `l4d2-server-setup` 完成系统接入、SSH/防火墙、并已用 SteamCMD 把 L4D2 本体装到 `/opt/l4d2`，已存在 `steam` 用户。还原前先把本地备份目录里的文件 `scp` 到新机 `/tmp/l4d2-restore/`。

### 步骤 0：网络加速优先（A8）—— 否则后续下载会很慢

```bash
# 还原 /etc/hosts CDN 块（把本地 network/hosts-cdn-block.txt 内容追加进去）
ssh mynew "sudo sed -i '/# L4D2-STEAM-CDN-BEGIN/,/# L4D2-STEAM-CDN-END/d' /etc/hosts"
ssh mynew "cat /tmp/l4d2-restore/network/hosts-cdn-block.txt | sudo tee -a /etc/hosts >/dev/null"
# 还原 gai.conf 强制 IPv4（仅当该行不存在时追加）
ssh mynew "grep -q '::ffff:0:0/96' /etc/gai.conf || (cat /tmp/l4d2-restore/network/gai.conf.line | sudo tee -a /etc/gai.conf >/dev/null)"
```

### 步骤 1：放置启动脚本 / 房间配置（A1 / A2）

```bash
ssh mynew "sudo cp /tmp/l4d2-restore/scripts/start_l4d2*.sh /opt/l4d2/ && sudo chmod +x /opt/l4d2/start_l4d2*.sh"
ssh mynew "sudo cp /tmp/l4d2-restore/cfg/server*.cfg /opt/l4d2/left4dead2/cfg/"
```

> 若新机 IP/端口/可见性策略变化，按 `l4d2-server-setup` 调整 `server*.cfg` 的 `sv_steamgroup` 等参数。

### 步骤 2：安装 systemd unit（A3）

```bash
ssh mynew "sudo cp /tmp/l4d2-restore/systemd/l4d2*.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable l4d2 l4d2_2"
```

### 步骤 3：还原 SourceMod 插件栈（A4）

> 前提：新机已按 `l4d2-plugin-manager` 装好 MetaMod:Source + SourceMod 框架（32-bit metamod.vdf）。然后覆盖回我们的 plugins/configs：

```bash
ssh mynew "sudo tar -xzf /tmp/l4d2-restore/sourcemod/sourcemod.tar.gz -C /opt/l4d2/left4dead2"
```

这会同时还原 `plugins/`（启用）与 `plugins/disabled/`（禁用态），保持原有启停状态。

### 步骤 4：重新编译自写插件（A5）—— 不搬二进制

```bash
# 把仓库里的 .sp 传上去，用 spcomp64 重新编译（见 l4d2-plugin-manager 细节）
scp deploy/l4d2-manager-web/plugins/infected_counter.sp mynew:/tmp/
ssh mynew "sudo chmod +x /opt/l4d2/left4dead2/addons/sourcemod/scripting/spcomp64"
ssh mynew "cd /opt/l4d2/left4dead2/addons/sourcemod/scripting && sudo -u steam ./spcomp64 /tmp/infected_counter.sp -o /opt/l4d2/left4dead2/addons/sourcemod/plugins/infected_counter.smx"
```

### 步骤 5：还原插件 VPK 与管理员白名单（A6 / A7）

```bash
ssh mynew "sudo cp /tmp/l4d2-restore/addons-vpk/*.vpk /opt/l4d2/left4dead2/addons/"
# 还原禁用态 VPK（保持原有启停状态）
ssh mynew "sudo mkdir -p /opt/l4d2/left4dead2/addons_disabled && (sudo cp /tmp/l4d2-restore/addons-vpk-disabled/*.vpk /opt/l4d2/left4dead2/addons_disabled/ 2>/dev/null || true)"
ssh mynew "sudo mkdir -p /opt/l4d2/left4dead2/ems/left4bots/cfg '/opt/l4d2/left4dead2/ems/admin system'"
ssh mynew "sudo cp /tmp/l4d2-restore/ems/l4b2-admins.txt /opt/l4d2/left4dead2/ems/left4bots/cfg/admins.txt"
ssh mynew "sudo cp /tmp/l4d2-restore/ems/adminsystem-admins.txt '/opt/l4d2/left4dead2/ems/admin system/admins.txt'"
```

### 步骤 6：统一文件归属

```bash
ssh mynew "sudo chown -R steam:steam /opt/l4d2/left4dead2/"
```

### 步骤 7：按 ID 重新下载地图（B1）

```bash
# 逐个按保留的 Workshop ID 重装（来源：webpanel/packages.json）
ssh mynew "sudo l4d2-add-map <Workshop_ID>"
# 或启用 Web 面板后用 Transfer 导入 packages.json，再逐个重新下载（见 l4d2-web-panel）
```

### 步骤 8：还原 Web 面板状态（A9，可选）

```bash
# 先按 l4d2-web-panel 部署面板，再覆盖 env 与来源记录
ssh mynew "sudo cp /tmp/l4d2-restore/webpanel/l4d2-manager-web.env /etc/l4d2-manager-web.env"
ssh mynew "sudo mkdir -p /var/lib/l4d2-manager-web && sudo cp /tmp/l4d2-restore/webpanel/packages.json /var/lib/l4d2-manager-web/packages.json"
```

### 步骤 9：启动并验证

```bash
ssh mynew "sudo systemctl restart l4d2 l4d2_2"
```

---

## 5. 还原后验证（只读健康检查）

```bash
ssh mynew "sudo systemctl status l4d2 l4d2_2 --no-pager"
ssh mynew "sudo ss -H -lunp 'sport = :27015'"
ssh mynew "sudo ss -H -lunp 'sport = :27016'"
# 插件栈还原确认（启用 + 禁用态都在）
ssh mynew "sudo find /opt/l4d2/left4dead2/addons/sourcemod/plugins -maxdepth 2 -name '*.smx' | sort"
# SourceMod 错误日志无新增 session（无 RCON 时以日志为准）
ssh mynew "sudo ls -t /opt/l4d2/left4dead2/addons/sourcemod/logs/errors_*.log | head -1"
# 网络加速生效确认
ssh mynew "getent ahosts cloud-3.steamusercontent.com | head -1; grep '::ffff:0:0/96' /etc/gai.conf"
```

判断标准与 `l4d2-troubleshooting` 一致：服务 `active (running)`、端口绑定、SM 日志无新报错、地图按 ID 逐个补齐。

---

## 6. 静态自检对照表（无新机时的完整性校验）

无法实测时，用下表确认「备份清单」与「还原步骤」一一对应、无遗漏、无孤儿项：

| 状态项 | 来源 skill | 备份步骤 | 还原步骤 |
| --- | --- | --- | --- |
| A1 启动脚本 | server-setup | §3 步骤1 | §4 步骤1 |
| A2 server*.cfg（含可见性/rcon） | server-setup | §3 步骤1 | §4 步骤1 |
| A3 systemd unit | server-setup | §3 步骤1 | §4 步骤2 |
| A4 SourceMod 插件栈 + disabled 态 | plugin-manager | §3 步骤1 | §4 步骤3 |
| A5 自写 .sp 源码 | plugin-manager | 随仓库 | §4 步骤4（spcomp64 重编译）|
| A6 插件 VPK | plugin-manager | §3 步骤1 | §4 步骤5 |
| A7 管理员白名单 | plugin-manager | §3 步骤1 | §4 步骤5 |
| A8 hosts CDN + gai.conf | server-setup / troubleshooting | §3 步骤1 | §4 步骤0 |
| A9 Web 面板 env + packages.json | web-panel | §3 步骤1 | §4 步骤8 |
| B1 地图 VPK（仅 ID） | map-manager / web-panel | §3 步骤3 | §4 步骤7 |
| B2 SteamCMD 缓存 | map-manager | 不迁移 | 由 ID 重下 |

自检要点：
- 每个 A 类项都有「备份→还原」闭环；每个还原步骤都有对应备份产物（无孤儿步骤）。
- B 类只迁移 ID，符合"地图大体积重下、插件完整迁移"的取舍。
- 敏感文件（A1/A2/A7/A9 env）只存本地私有路径，文档示例用占位符。
