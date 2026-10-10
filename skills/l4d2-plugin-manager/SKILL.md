---
name: "l4d2-plugin-manager"
description: "L4D2 服务器插件与 Mod 管理。当需要安装 VPK 插件（Left 4 Bots 2 / Left 4 Lib / Admin System）、设置游戏内管理员权限、管理 MetaMod+SourceMod 服务器插件栈、自写 SourcePawn 源码并在服务器用 spcomp64 编译、通过 Web 面板动态扫描启停 .smx、或回滚插件改动时调用。不负责服务器搭建、地图管理或 Web 面板部署。"
---

# L4D2 插件与 Mod 管理

本 skill 覆盖两类插件：① VPK 形态的 Mod（创意工坊 addons）；② MetaMod:Source + SourceMod 的服务器侧 `.smx` 插件栈（含自写 SourcePawn + spcomp64 编译）。服务器搭建/systemd 见 `l4d2-server-setup`；地图管理见 `l4d2-map-manager`；报错排查见 `l4d2-troubleshooting`；Web 面板部署见 `l4d2-web-panel`。

> 安全规范：回滚、删除插件或重启房间前，先确认影响范围和当前是否有人在线。两个房间共享同一 `/opt/l4d2/left4dead2/` 目录，SourceMod 插件改动会同时影响两个房间。不要把 RCON 密码、GSLT、Steam token、SSH 私钥写入公开文档。

## 当前启用的 SourceMod 业务插件快照

> 更新时间：2026-10-10，由 `myubuntu2` 只读核验。

- `left4dhooks.smx`：核心 hooks/gamedata 依赖库（**受保护，不可从面板禁用**）。
- `l4d_infected_hp.smx`：Tank / Witch / 特感血量显示。
- `infected_counter.smx`：自写插件，聊天区周期播报「特感: X 普感: Y」。
- `jiangmen_changelevel_fix.smx`：自写插件，江门新会切图修复。
- `showdamage.smx`：显示自己造成的伤害数值（聊天区）。
- `l4d2_sb_fix.smx`：求生 Bot 行为增强 / 修复。
- 其余启用项为 SourceMod 自带 base/admin 系列（`basecommands`、`adminmenu`、`funcommands`、`playercommands` 等）。

**禁用态**（`plugins/disabled/`，禁用态本身是状态，备份/迁移必须一起带走）：`advertisements.smx`（含他人信息）、`l4d_kill.smx`（实为 `!zs` 自杀命令）、`mapchooser.smx` / `nextmap.smx` / `rockthevote.smx` / `nominations.smx` / `randomcycle.smx`（L4D2 投票链不兼容）、`sql-admin-manager.smx` / `admin-sql-prefetch.smx` / `admin-sql-threaded.smx`（改用 flatfile）。

**插件类 VPK**：当前机器**未安装** Left 4 Bots 2 —— `addons/` 下无 `left4bots2.vpk` / `left4lib.vpk` / `admin_system.vpk`，`ems/` 下无 `left4bots`（仅剩 `ems/lxc`）。下方 L4B2 安装章节属于可选增强，装之前先评估与现有 SourceMod 栈的冲突。

---

## 1. 插件与 Mod 管理 (VPK Addons)

除了地图，服务器还可以通过 VPK 插件增强功能（如提升 Bot 智商、增加管理员菜单）。

### A. 常用插件推荐
- **Left 4 Bots 2** (ID: `2279814689`)：极大提升 Bot 智商，支持指令指挥。*（依赖 Left 4 Lib）*
- **Left 4 Lib** (ID: `2634208272`)：核心前置库。
- **Admin System** (ID: `213591107`)：提供游戏内管理员指令（如 `!give`, `!kick`）。

### B. 快速安装 Mod (API 直链方式)
**不要使用官方 `steamcmd` 下载 Mod**，因为其在国内极易失败。建议使用以下流程：

1.  **获取直链**：
    ```bash
    ssh myubuntu2 "curl -s -d 'itemcount=1&publishedfileids[0]=<Mod_ID>' -X POST https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
    ```
2.  **下载并部署**：
    ```bash
    # 在服务器执行
    curl -L -o /tmp/mod.vpk "<file_url>"
    sudo cp /tmp/mod.vpk /opt/l4d2/left4dead2/addons/
    sudo chown steam:steam /opt/l4d2/left4dead2/addons/mod.vpk
    sudo systemctl restart l4d2        # Room 1
    sudo systemctl restart l4d2_2      # Room 2 如需同步生效
    ```

### C. 设置管理员权限 (EMS 插件)
对于 **Left 4 Bots** 或 **Admin System**，需要将你的 SteamID 加入白名单：
- **文件路径**：
  - L4B2: `/opt/l4d2/left4dead2/ems/left4bots/cfg/admins.txt`
  - Admin System: `/opt/l4d2/left4dead2/ems/admin system/admins.txt`
- **格式**：`STEAM_1:0:XXXXXXXX //你的昵称`

---

## 2. SourceMod 服务器插件栈

当需要安装服务器侧功能插件（统计、血量显示、伤害显示、感染者计数、Bot 增强）时，优先使用 **MetaMod:Source + SourceMod**，不要把这类功能混进 Workshop VPK 管理。

> 经验沉淀：很多 wyxls / 第三方 `.smx` 要么硬编码他人信息、要么和 L4D2 投票链不兼容、要么名实不符。**优先自写 SourcePawn 源码并在服务器上用 `spcomp64` 编译**，可控、可读、无他人信息，规避兼容性未知风险。

### A. 当前实际启用的插件（保守稳定包）

经清理后，默认只保留下列业务插件，其余一律移入 `plugins/disabled/`：

- **Left 4 DHooks Direct**（`left4dhooks.smx`）：核心 hooks/gamedata 依赖库。**受保护**，缺失会导致大量插件无法加载，面板禁止禁用。
- **Infected Health Gauge**（`l4d_infected_hp.smx`）：Tank、Witch、特感血量显示。
- **Infected Counter**（`infected_counter.smx`）：自写插件，聊天区周期播报「特感: X 普感: Y」。
- **Show Damage**（`showdamage.smx`）：显示自己造成的伤害数值（聊天区）。
- **Survivor Bot Fix**（`l4d2_sb_fix.smx`）：提升单人 / Bot 局体验。

已禁用且**不应**默认启用：

- `advertisements.smx`：配置 `configs/advertisements.txt` 是 wyxls 仓库样例，硬编码了他人信息（"本服务器由 xx 提供"、管理员昵称），是广播他人信息的根因。
- `l4d_kill.smx`：面板曾误标为 "Kill Counter / 击杀计数"，源码实际只注册 `sm_zs`/`!zs` 自杀命令，**无任何计数功能**，名实不符。
- `mapchooser.smx` / `nextmap.smx`：L4D2 用 mission/cfg 而非 mapcycle，不兼容，持续刷错误日志。
- `rockthevote.smx` / `nominations.smx`：依赖 `mapchooser`，连带报 `Could not find required plugin mapchooser`。

安装框架注意：
- L4D2 Linux dedicated server 是 32-bit。`metamod.vdf` 应指向 `../left4dead2/addons/metamod/bin/server`，并禁用或删除官方包里的 `metamod_x64.vdf`，否则会报 `wrong ELF class: ELFCLASS64`。
- SourceMod stable tarball 不只包含 `addons/sourcemod`，还包含 `cfg/sourcemod/sourcemod.cfg`；如果日志出现 `couldn't exec sourcemod/sourcemod.cfg`，需要补解压 `cfg/sourcemod/` 到 `/opt/l4d2/left4dead2/cfg/sourcemod/`。
- 服务器未配 `rcon_password`，无法 `sm plugins list`，验证以读 SourceMod 错误日志为准。

### B. 自写 SourcePawn 插件 + 服务器编译（spcomp64）

当现成插件不可靠时，自己写 `.sp` 源码并在服务器上编译。源码统一放在仓库 `deploy/l4d2-manager-web/plugins/`（如 `infected_counter.sp`）。

部署流程：
```bash
# 1. 本地写好 .sp 源码后传到服务器临时目录
scp deploy/l4d2-manager-web/plugins/infected_counter.sp myubuntu2:/tmp/

# 2. 备份当前插件栈（PowerShell 侧先生成时间戳，避免 $(date) 被本地解析）
#    $ts = Get-Date -Format "yyyyMMddHHmmss"
ssh myubuntu2 "sudo tar -czf /opt/l4d2/left4dead2/addons/sm_plugins_backup_<时间戳>.tar.gz -C /opt/l4d2/left4dead2/addons sourcemod/plugins sourcemod/configs"

# 3. 用 spcomp64 编译（关键：spcomp 是 32-bit 且原文件常无执行位，必须用 spcomp64 并 chmod +x）
ssh myubuntu2 "sudo chmod +x /opt/l4d2/left4dead2/addons/sourcemod/scripting/spcomp64"
ssh myubuntu2 "cd /opt/l4d2/left4dead2/addons/sourcemod/scripting && sudo -u steam ./spcomp64 /tmp/infected_counter.sp -o /tmp/infected_counter.smx"

# 4. 部署（带时间戳备份旧产物）+ 归属 steam + 重启两房间
ssh myubuntu2 "sudo cp /opt/l4d2/left4dead2/addons/sourcemod/plugins/infected_counter.smx /tmp/infected_counter.smx.bak-<时间戳> 2>/dev/null; sudo cp /tmp/infected_counter.smx /opt/l4d2/left4dead2/addons/sourcemod/plugins/ && sudo chown steam:steam /opt/l4d2/left4dead2/addons/sourcemod/plugins/infected_counter.smx"
ssh myubuntu2 "sudo /usr/local/bin/l4d2-webctl restart-room all"
```

> 注意：仓库 helper `l4d2-webctl` 内的 `compile_source_plugin()` 仍调用 `spcomp`；服务器实际可用的是 `spcomp64`。手动编译时务必用 `spcomp64`。

#### L4D2 插件开发两个关键陷阱

1. **L4D2 客户端不支持左上 HUD**：`ShowSyncHudText` / `CreateHudSynchronizer` 的左上区域在 L4D2 客户端不可见或不稳定；`PrintHintText` 会触发提示音、闪烁，且会被游戏 tutor 提示顶掉。**最稳定的玩家可见通道是 `PrintToChatAll`（聊天区）。** `infected_counter` 最终即采用聊天区显示。`showdamage` 也通过 `sm_show_damage_text_area "3"` 改为聊天区显示。
2. **`TIMER_FLAG_NO_MAPCHANGE` 换图后被杀**：带此 flag 的 `CreateTimer` 在换图后会被销毁，插件文件还在但循环停止（表现为"刚加载能显示、换一张图就不显示了"）。修复方法：在 `OnMapStart()` 里重建 timer（`OnMapEnd()` 把句柄置 `INVALID_HANDLE`）。

`infected_counter` 计数逻辑参考：
- 特感：遍历 `1..MaxClients`，`IsClientInGame(i) && GetClientTeam(i)==3 && IsPlayerAlive(i)`。
- 普感：`int ent=-1; while((ent=FindEntityByClassname(ent,"infected"))!=-1) count++;`
- 播报间隔由 ConVar `l4d_infcount_chat_interval`（默认 20 秒）控制，`l4d_infcount_enable` 开关。

### C. Web 面板管理方式（动态扫描）

面板的"服务器插件"栏管理 SourceMod `.smx`，已改为**动态扫描**，不再局限于预置清单：
- `server_plugins_snapshot()` 同时扫描 `plugins/`（启用）与 `plugins/disabled/`（禁用）下的所有 `*.smx`，因此**任何新装的插件**（含自写的 `infected_counter.smx`）都会自动出现在面板上，可单独启用/禁用。
- 启用/禁用通过在 `plugins/` 与 `plugins/disabled/` 间 `move` 文件实现（`set-server-plugin-state`），随后需重启对应房间。
- `left4dhooks.smx` 在 `PROTECTED_PLUGIN_FILES` 中，**受保护，禁止禁用**（缺失会让大量插件崩）。
- 面板友好标签由 `SERVER_PLUGIN_LABELS` 提供（例如把 `l4d_kill.smx` 标注为 `Self-Kill Command (!zs)` 而非误导性的 Kill Counter）；未登记的插件直接显示文件名。
- 命令行等效：`l4d2-webctl set-server-plugin-state <plugin_file.smx|managed_id> <enabled|disabled>`，支持直接传 `xxx.smx` 文件名。
- 两个房间共享同一 `left4dead2` 目录，SourceMod 插件改动会同时影响两个房间。

> Web 面板的部署、安全边界与验证脚本见 `l4d2-web-panel`。

### D. 常用验证命令

安装/改动后先做只读验证：
```bash
ssh myubuntu2 "sudo systemctl status l4d2 l4d2_2 --no-pager"
ssh myubuntu2 "sudo ss -H -lunp 'sport = :27015'"
ssh myubuntu2 "sudo ss -H -lunp 'sport = :27016'"
ssh myubuntu2 "sudo find /opt/l4d2/left4dead2/addons/sourcemod/plugins -maxdepth 2 -type f -name '*.smx' | sort"
# 重启后确认 SM 错误日志无新增 session（无 RCON，以日志为准）
ssh myubuntu2 "sudo ls -t /opt/l4d2/left4dead2/addons/sourcemod/logs/errors_*.log | head -1"
```

游戏内或服务器控制台验证：
```text
meta version
sm version
sm plugins list
```

### E. 回滚

如果安装后房间崩溃或无法加载：
- 先从 Web 面板（或 `set-server-plugin-state ... disabled`）禁用可疑 `.smx` 并重启两个房间。
- 自写插件是纯新增文件，移到 `plugins/disabled/` 即可完全复原。
- 整体回滚：解压最近的 `sm_plugins_backup_<时间戳>.tar.gz` 覆盖 `plugins/`，`sudo chown -R steam:steam sourcemod`，重启房间。
- 因全程只 `move` 未删除，禁用项均原样保留在 `plugins/disabled/`，可随时复原。
- 回滚、删除插件或重启房间前，需要确认影响范围和当前是否有人在线。
