---
name: "l4d2-manager"
description: 'L4D2 专用服务器管理的总入口与导航。当用户给出宽泛的“管理 L4D2 服务器”意图、不确定该用哪个子能力，或需要服务器运行形态概览、安全规范、常用管理指令快速参考时调用。具体操作请按本索引路由到 l4d2-server-setup / l4d2-map-manager / l4d2-plugin-manager / l4d2-troubleshooting / l4d2-web-panel / l4d2-backup-migrate。'
---

# L4D2 服务器管理总入口（索引 / 路由）

本 skill 是 L4D2 专用服务器管理的导航入口。详细操作已拆分到 6 个聚焦子 skill，请按下表路由到对应 skill 再展开操作。

## 当前服务器快照

> 更新时间：2026-10-10，由 `myubuntu2` 只读核验得出。记录运行形态和排障入口，不记录真实 RCON 密码、GSLT、Steam token 等敏感信息。

**当前生产机：`myubuntu2`（主机名 `l4d2-server`，Ubuntu 20.04 LTS）。**
旧机别名 `myubuntu`（121.5.28.16）**已不可达**（SSH 22 端口连接被远端关闭），仅作历史记录保留，不要再对它执行命令。

| 房间 | 服务 | 端口 | 配置文件 | 默认地图 | 可见性 |
| --- | --- | --- | --- | --- | --- |
| Room 1 | `l4d2.service` | `27015/udp` | `server.cfg` | `l4d2_bts01_forest` | Steam 组内专属（`sv_steamgroup_exclusive 1`） |
| Room 2 | `l4d2_2.service` | `27016/udp` | `server_2.cfg` | `glubtastic5_1` | 公开可搜（`sv_steamgroup_exclusive 0`） |

- 两房间同属 Steam 组 `46097240`；`sv_lan 0`、`sv_region 4`；均未设 `sv_password`。
- 安装目录：`/opt/l4d2`，由非 root 用户 `steam` 运行；两房间共享 `/opt/l4d2/left4dead2/`。
- 本地 SSH 别名 `myubuntu2`，大量命令形如 `ssh myubuntu2 "sudo systemctl status l4d2"`。
- 启动参数均含 `+sv_hibernate_when_empty 0`（保证 RCON 可用）。
- **插件栈形态已变更**：新机不再安装 Left 4 Bots 2（`addons/` 下无 `left4bots2.vpk` / `left4lib.vpk` / `admin_system.vpk`，`ems/` 下无 `left4bots`），改为纯 MetaMod:Source + SourceMod + Left4DHooks 方案。
- 启用的业务 `.smx`：`left4dhooks.smx`、`l4d_infected_hp.smx`、`infected_counter.smx`（自写）、`jiangmen_changelevel_fix.smx`（自写）、`showdamage.smx`、`l4d2_sb_fix.smx`；其余为 SourceMod 自带 base/admin 系列。
- 禁用的 `.smx`（禁用态本身是状态，备份/迁移必须一起带走）：`advertisements`、`mapchooser`、`nextmap`、`randomcycle`、`rockthevote`、`nominations`、`l4d_kill`、`sql-admin-manager`、`admin-sql-prefetch`、`admin-sql-threaded`。
- 地图：`maps/` 下 65 个 `.bsp`；`addons/` 下 12 个 VPK，主要为 Back To School 系列、`Glubtastic 5`、`Ladder to Heaven 3` 及 3 个 mod VPK；`addons_disabled/` 为空。
- Web 面板已部署：`l4d2-manager-web.service` enabled/active，监听 `8080/tcp`，`Server: L4D2Manager/0.3`；状态目录 `/var/lib/l4d2-manager-web/`（`jobs/`、`packages.json`、`uploads/`、`exports/`）。
- 网络加速：`/etc/hosts` 含 `L4D2-STEAM-CDN` 标记块，`/etc/gai.conf` 已加 `precedence ::ffff:0:0/96 100` 强制 IPv4。
- 防火墙：`ufw` 已放行 `22/tcp`、`27015/udp`、`27016/udp`、`8080/tcp`（含 IPv6 对应规则）。

### 当前已知风险

- **磁盘偏紧**：`/` 40G 已用 32G，仅剩 6.4G（84%）。安装新地图或备份前先查 `df -h /` 与 `addons/`、`maps/` 占用。
- **下载代理可能已断**：面板 env 仍配置 `L4D2_DOWNLOAD_PROXY=http://127.0.0.1:7890`，但 `mihomo` 服务当前 **inactive**。走代理的搜索/下载会失败，改用服务器直连前先确认。

## 子 skill 导航

| 子 skill | 触发场景 |
| --- | --- |
| `l4d2-server-setup` | 新服务器首次接入、SSH 加固与防火墙、Steam CDN/代理、systemd 服务安装运行、多房间（多实例）配置、房间公开/私密可见性、GSLT 申请配置 |
| `l4d2-map-manager` | 安装创意工坊地图、VPK 资源提取、修改默认启动地图、RCON 实时切图、已装地图快速切换、存储清理、本地地图备份与应急恢复 |
| `l4d2-plugin-manager` | 安装 VPK 插件 Mod（Left 4 Bots 2 等）、设置游戏内管理员权限、MetaMod+SourceMod 插件栈、自写 SourcePawn + spcomp64 编译、面板动态扫描启停 `.smx`、插件回滚 |
| `l4d2-troubleshooting` | 标准健康检查、日志噪声定位、KeyValues Error 修复、权限问题、IPv6/gai.conf 强制 IPv4、客户端重复下载等 FAQ |
| `l4d2-web-panel` | 部署/更新 Web 管理面板、了解面板功能边界与 sudoers 安全白名单、运行面板验证脚本 |
| `l4d2-backup-migrate` | 服务器到期/换机时的完整状态备份与新机迁移还原（配置/插件/权限/网络加速完整迁移，地图仅保留 Workshop ID 重下）|

## 安全规范（所有子 skill 通用）

以下内容只允许保存在服务器配置或本机私有环境中，不要写入公开文档、Issue、提交说明或聊天记录：
- `rcon_password` 的真实值。
- `+sv_setsteamaccount` 后面的 GSLT。
- Steam API、代理订阅、SSH 私钥、Web 登录密码、服务器登录凭据。

展示命令输出前，尤其是 `systemctl status`、`systemctl cat`、`start_l4d2*.sh`、`server*.cfg`，需要先把 token 和密码替换成占位符，例如 `YOUR_RCON_PASSWORD`、`YOUR_GSLT_TOKEN`。改变服务器状态（重启、切图、删除文件）前，先确认目标房间、影响范围和当前是否有人在线，并优先做只读健康检查。

## 常用管理指令快速参考

- **查看服务状态**：`ssh myubuntu2 "sudo systemctl status l4d2"`（Room 1）或 `l4d2_2`（Room 2）
- **重启服务**：`ssh myubuntu2 "sudo systemctl restart l4d2"`
- **查看实时日志**：`ssh myubuntu2 "sudo journalctl -u l4d2.service -f"`
- **查看端口监听**：`ssh myubuntu2 "sudo ss -H -lunp 'sport = :27015'"` 或 `27016`
- **查看最近错误**：`ssh myubuntu2 "sudo journalctl -u l4d2 -u l4d2_2 --since '24 hours ago' --no-pager | grep -Ei 'error|fail|warning|missing|keyvalues' | tail -80"`

更深入的健康检查与排障见 `l4d2-troubleshooting`；地图/插件/搭建的完整流程见对应子 skill。
