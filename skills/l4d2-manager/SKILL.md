---
name: "l4d2-manager"
description: 'L4D2 专用服务器管理的总入口与导航。当用户给出宽泛的“管理 L4D2 服务器”意图、不确定该用哪个子能力，或需要服务器运行形态概览、安全规范、常用管理指令快速参考时调用。具体操作请按本索引路由到 l4d2-server-setup / l4d2-map-manager / l4d2-plugin-manager / l4d2-troubleshooting / l4d2-web-panel / l4d2-backup-migrate。'
---

# L4D2 服务器管理总入口（索引 / 路由）

本 skill 是 L4D2 专用服务器管理的导航入口。详细操作已拆分到 6 个聚焦子 skill，请按下表路由到对应 skill 再展开操作。

## 当前服务器快照

> 更新时间：2026-06-18。记录运行形态和排障入口，不记录真实 RCON 密码、GSLT、Steam token 等敏感信息。

| 房间 | 服务 | 端口 | 配置文件 | 默认地图 | 可见性 |
| --- | --- | --- | --- | --- | --- |
| Room 1 | `l4d2.service` | `27015/udp` | `server.cfg` | `hls_05` | Steam 组内/私密 |
| Room 2 | `l4d2_2.service` | `27016/udp` | `server_2.cfg` | `zc_m1` | 公开可搜 |

- 安装目录：`/opt/l4d2`，由非 root 用户 `steam` 运行；两房间共享 `/opt/l4d2/left4dead2/`。
- 本地 SSH 别名 `myubuntu`，大量命令形如 `ssh myubuntu "sudo systemctl status l4d2"`。
- 当前主要 VPK：地图 `gzzc7.3.vpk`、`tianti.vpk`；插件 `left4bots2.vpk`、`left4lib.vpk`、`admin_system.vpk`。
- 当前启用的 SourceMod 业务插件：`left4dhooks.smx`（受保护）、`l4d_infected_hp.smx`、`infected_counter.smx`（自写）、`showdamage.smx`、`l4d2_sb_fix.smx`。

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

- **查看服务状态**：`ssh myubuntu "sudo systemctl status l4d2"`（Room 1）或 `l4d2_2`（Room 2）
- **重启服务**：`ssh myubuntu "sudo systemctl restart l4d2"`
- **查看实时日志**：`ssh myubuntu "sudo journalctl -u l4d2.service -f"`
- **查看端口监听**：`ssh myubuntu "sudo ss -H -lunp 'sport = :27015'"` 或 `27016`
- **查看最近错误**：`ssh myubuntu "sudo journalctl -u l4d2 -u l4d2_2 --since '24 hours ago' --no-pager | grep -Ei 'error|fail|warning|missing|keyvalues' | tail -80"`

更深入的健康检查与排障见 `l4d2-troubleshooting`；地图/插件/搭建的完整流程见对应子 skill。
