# L4D2 服务器基础配置与地图管理指南 🎮

[English](./README.en.md) | 简体中文

本指南记录了从零开始配置 L4D2 (Left 4 Dead 2) 专用服务器的全过程，包括环境优化、网络加速、基础安装以及后续的自动化地图管理方案。

---

## 项目定位

这是一个面向 L4D2 服主的服务器管理 Skill / Playbook 与运维参考仓库。它把服务器检查、地图安装、RCON 切图、多房间管理、日志排障和敏感信息脱敏流程整理成一份可复用的操作手册。

仓库内提供了可直接安装或引用的 [skills/l4d2-manager/SKILL.md](./skills/l4d2-manager/SKILL.md)，但核心内容并不绑定某一个工具。你也可以把这份文档作为 Codex、Cursor、Trae、Windsurf、Claude Code、GitHub Copilot Chat 等 AI IDE/Agent 的项目上下文，或者直接作为人工运维手册使用。

适合：
- 已经有一台 Linux L4D2 专用服务器，希望用 AI IDE、Agent 或普通 SSH 流程辅助管理。
- 需要维护创意工坊地图、VPK、插件、RCON 和 Systemd 服务。
- 想把个人服务器运维流程沉淀成可审计、可复用的文档。

不适合：
- 完全替代服务器安全加固或云厂商防火墙配置。
- 保存真实 RCON 密码、GSLT、SSH 私钥、代理订阅等敏感信息。
- 在未确认命令影响的情况下自动执行删除、重启或覆盖操作。

---

## 快速开始

### 作为 Codex Skill 使用

将仓库中的 skill 目录复制到 Codex 用户 skill 目录：

```powershell
Copy-Item -Recurse .\skills\l4d2-manager "$env:USERPROFILE\.codex\skills\l4d2-manager"
```

安装后重启 Codex，让新 skill 被加载。后续可以在对话中使用 `$l4d2-manager`，或直接描述 L4D2 服务器管理任务。

### 在其他 AI IDE 或 Agent 中使用

如果你的工具支持项目规则、上下文文档或自定义 instructions，可以把以下文件加入上下文：

- `skills/l4d2-manager/SKILL.md`
- `L4D2_MAP_SKILL.md`
- `README.md`

推荐把任务描述写成“请按本仓库的 L4D2 server management playbook 执行”，并要求工具在执行前先确认目标房间、目标地图、是否涉及重启、是否涉及敏感信息输出。

### Trae 等工具的兼容使用

仓库只维护一份 canonical skill 文件：`skills/l4d2-manager/SKILL.md`。如果某个工具需要 `.trae/skills/...` 这样的固定目录，可以在本地复制一份：

```powershell
Copy-Item -Recurse .\skills\l4d2-manager .\.trae\skills\l4d2-manager
```

这样可以避免仓库中长期维护两份内容相同的 `SKILL.md`，降低后续更新时两边漂移的风险。

### 推荐准备

- 在本地 `~/.ssh/config` 配好服务器别名，例如 `myubuntu`。
- 在服务器侧使用非 root 用户运行 L4D2，例如 `steam`。
- 将真实密码和 token 只保存在服务器配置或本机私有环境中。
- 先阅读 [L4D2_MAP_SKILL.md](./L4D2_MAP_SKILL.md) 中的敏感信息处理规范和健康检查命令。

### 示例提示词

```text
$l4d2-manager 检查当前两个房间的运行状态
$l4d2-manager 查看最近 24 小时的 L4D2 错误日志并判断是否影响玩家
$l4d2-manager 帮我把 Workshop 地图 3526529688 安装到服务器
$l4d2-manager 将 Room 2 切换到 zc_m1，并说明是否需要重启
$l4d2-manager 检查 addons、maps、workshop 缓存占用，给出清理建议
```

---

## 🌟 核心特性
- **网络优化**：针对国内环境的 Steam CDN 节点加速方案。
- **自动化管理**：集成 Clash + Proxychains 的网络代理方案，确保 `steamcmd` 稳定运行。
- **手动提取**：推荐的 VPK 资源提取方案，提升服务器稳定性。
- **快速切图**：详细的 RCON 远程指令集，实现秒级地图切换。
- **远程管理**：配置 SSH 别名，简化服务器维护操作。
- **故障排查**：针对常见报错（如 KeyValues Error）的修复指南。
- **安全脱敏**：公开文档只使用占位符，不记录真实 RCON、GSLT、Steam token 或 SSH 凭据。

---

## 🛠 1. 服务器基础环境配置
在安装游戏之前，为了解决国内服务器访问 Steam 网络慢、下载失败的问题，需要执行以下核心配置：
- **Steam CDN 优化**：修改 `/etc/hosts` 指向高速节点。
- **网络代理配置**：使用 Clash + Proxychains4 转发 `steamcmd` 流量。

## 🚀 2. L4D2 服务安装与运行
- **安装路径**：`/opt/l4d2`，由非 root 用户 `steam` 运行。
- **启动脚本**：定义核心参数如 `+sv_hibernate_when_empty 0` 以确保 RCON 可用。
- **系统服务**：使用 Systemd 实现崩溃自启，当前维护 `l4d2` 与 `l4d2_2` 两个房间。

## 🧭 当前服务器形态
- **Room 1**：`l4d2.service`，端口 `27015/udp`，默认地图 `hls_05`，偏 Steam 组内/私密。
- **Room 2**：`l4d2_2.service`，端口 `27016/udp`，默认地图 `zc_m1`，公开可搜。
- **常用检查**：服务状态、端口监听、最近错误日志已整理到详细 Skill 文档中。

## 🗺 3. 地图安装与管理
- **自动安装**：使用 `l4d2-add-map` 脚本或 Steam API 下载。
- **手动提取**：使用 `vpk_extract.py` 将 VPK 内容提取到游戏目录（推荐）。
- **默认地图**：修改 `start_l4d2.sh` 中的 `+map` 参数。

## ⚡ 4. 实时切换地图 (RCON)
无需重启服务器，在游戏控制台中：
1. `rcon_password "YOUR_RCON_PASSWORD"`
2. `rcon changelevel <map_name>`
3. 查看可用地图：`ls /opt/l4d2/left4dead2/maps/*.bsp`

## 🧹 5. 存储管理与清理
定期清理以下目录以释放空间：
- `/opt/l4d2/left4dead2/addons/` 中的旧 VPK。
- `/home/steam/Steam/steamapps/workshop/content/550/` 下的下载缓存。

## 🔧 6. 故障排查与 SSH 技巧
- **KeyValues Error**：修复 BOM 头 or 括号不匹配。
- **SSH 别名**：在本地 `~/.ssh/config` 配置别名，实现一键连接。

## 💾 7. 本地备份与恢复
- **备份目录**：在本地 `addons/workshop_backup` 存放稳定的 VPK 文件。
- **应急恢复**：当遇到地图反复下载或丢失时，手动将备份文件移动到 `addons` 根目录。

## ❓ 8. 常见问题 (FAQ)
- **客户端下载问题**：解释了为什么服务器安装后客户端仍需下载（Source 引擎架构）。
- **版本校验不一致**：提供了解决地图反复下载的彻底方案。

---

## 📄 详细文档
更多详细步骤和命令请参考 [L4D2_MAP_SKILL.md](./L4D2_MAP_SKILL.md)。

---

## 🔗 更多资源
- [GitHub Profile](https://github.com/Wizard23333)
- [个人博客](https://wizard23333.github.io/)

---
*Generated on: 2026-04-26*
