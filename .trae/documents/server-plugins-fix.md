# 服务器插件修复与清理计划

> 状态：**已执行并验证完成**（2026-06-14）。本文档为执行记录 + 回滚预案。
> 本计划文件曾因上下文丢失而消失，现据线上实际状态重建，确保回滚预案可追溯。

## Summary

服务器装了 4 个业务插件，但体验下来只有「特感血量显示」正常，其余不工作，且某插件错误地广播「本服务器由 xx 提供」。目标：保留正常插件，修复或止血其余插件，去除他人广播信息，并提供完整备份/回滚预案。

## Current State Analysis（诊断结论）

插件目录：`/opt/l4d2/left4dead2/addons/sourcemod/plugins`（启用） 与 `plugins/disabled/`（禁用），两房间 `l4d2`@27015 / `l4d2_2`@27016 共用同一 addons 目录。

四个「业务」插件实际情况：

1. `l4d_infected_hp.smx`（特感血量显示）—— **正常**，保留。
2. `left4dhooks.smx`（依赖库）—— 正常，保留（被血量插件依赖）。
3. `advertisements.smx`（广播）—— 配置 `configs/advertisements.txt` 是从 wyxls 仓库原样拷贝的样例，硬编码了他人信息（"这是Zakikun的高级难度求生服务器…"、"服务器管理员: Zakikun、kings"），即「本服务器由 xx 提供」的根因。
4. `l4d_kill.smx`（面板误标为 "Kill Counter 击杀计数"）—— 源码（wyxls 仓库，作者 Danny & FlamFlam & Zakikun）实际只注册 `sm_zs`/`!zs` 自杀命令，**无任何计数功能**，与面板标签不符。

附带不兼容项：`mapchooser.smx` / `nextmap.smx` 在 L4D2 不兼容（L4D2 用 mission/cfg 而非 mapcycle），持续刷错误日志；`rockthevote.smx` / `nominations.smx` 依赖 `mapchooser`，会连带报 "Could not find required plugin mapchooser"。

服务器未配 `rcon_password`，无法 `sm plugins list`，改用读 SM 错误日志验证。

## Proposed Changes（已执行步骤）

- **步骤 0 — 全量备份**：`tar` 备份 `plugins/`、`configs/`、`metamod.vdf` 到
  `/opt/l4d2/left4dead2/addons/sm_plugins_backup_20260614123821.tar.gz`（30.5MB）。全程只 `move` 不删除，任意一步可逆。
- **步骤 1 — 禁用广播插件**：`l4d2-webctl set-server-plugin-state advertisements disabled`（用户决定：直接禁用，不重写他人配置）。
- **步骤 2 — 禁用不兼容地图投票链**：`mv mapchooser.smx disabled/`，并连带 `mv rockthevote.smx nominations.smx disabled/` 止血。
- **步骤 3 — 禁用 l4d_kill**：`l4d2-webctl set-server-plugin-state kill_counter disabled`（用户确认：直接禁用 `l4d_kill.smx`）。
- **步骤 4 — 重启两房间**：`restart-room all`，最终重启 13:09:38。
- **步骤 5 — 验证**：见下。

最终启用的业务插件：仅 `l4d_infected_hp.smx` + `left4dhooks.smx`（其余为 SourceMod 自带基础插件）。

## Assumptions & Decisions（用户已确认）

- 广播插件 → 直接禁用（不维护他人配置）。
- 不工作的插件 → 优先尝试修复使其真正生效；经诊断 l4d_kill 无业务价值，用户确认禁用。
- nextmap/mapchooser → 一起禁用止血（含其依赖链 rockthevote/nominations）。
- 改造形式 → 一次性运维调好；可立即重启。

## 回滚预案

1. **整体回滚**（恢复到改造前）：
   ```bash
   cd /opt/l4d2/left4dead2/addons
   tar -xzf sm_plugins_backup_20260614123821.tar.gz   # 覆盖 plugins/ configs/ metamod.vdf
   sudo chown -R steam:steam sourcemod
   l4d2-webctl restart-room all
   ```
2. **单插件回滚**（重新启用某插件）：把对应 `.smx` 从 `plugins/disabled/` 移回 `plugins/`，重启房间。例如恢复广播：
   `l4d2-webctl set-server-plugin-state advertisements enabled && l4d2-webctl restart-room all`。
3. 因全程只 move 未删除，禁用项均原样保留在 `plugins/disabled/`，可随时复原。

## Verification（已通过）

- `systemctl is-active l4d2 l4d2_2` → 均 `active`。
- 端口 27015 / 27016 监听正常。
- SM 错误日志：最后一次 error session 为 12:53（禁用前的瞬时 rockthevote/nominations 报错），**13:09 最终重启后零新增报错**。
- 备份文件存在：`sm_plugins_backup_20260614123821.tar.gz`。
