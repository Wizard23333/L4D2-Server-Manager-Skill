# 感染者数量显示插件（自写 + 服务器编译）

> 状态：**已执行并验证完成（2026-06-14 13:29）**。本次仅新增一个「常驻 HUD 实时显示特感/普感数量」的自写插件，在服务器上用 spcomp64 编译，不安装其他额外插件。
>
> 执行记录：备份 `sm_plugins_backup_20260614132659.tar.gz`；源码 `deploy/l4d2-manager-web/plugins/infected_counter.sp` → scp `/tmp` → **spcomp64**（注意：spcomp 是 32-bit 且原文件无执行位，须 chmod +x 并改用 spcomp64）编译 → `plugins/infected_counter.smx`（3324 字节，零告警）→ chown steam → restart-room all。验证：两房间 active、端口正常、13:29 重启后错误日志零新增 session。

## Summary

用户需要一个常驻 HUD、实时刷新、显示当前「特感数量 + 普感数量」的插件。决定自己用 SourcePawn 写一个轻量插件，scp 源码到服务器用现成的 `spcomp` 编译为 `.smx`，启用并重启两房间。全程做好备份/回滚。

不安装其他第三方插件（用户选择「暂不安装额外的」）。

## Current State Analysis

- 插件目录：`/opt/l4d2/left4dead2/addons/sourcemod/plugins`（启用） / `plugins/disabled/`（禁用）。两房间 `l4d2`@27015、`l4d2_2`@27016 共用同一 addons 目录。
- 当前启用业务插件：`l4d_infected_hp.smx`（特感血量）+ `left4dhooks.smx`（依赖库）。
- **服务器具备编译能力**：`/opt/l4d2/left4dead2/addons/sourcemod/scripting/spcomp` 存在（steam:steam，1.08MB），`include/` 下含标准 + left4dhooks 头文件。可在服务器侧编译 `.sp` → `.smx`，无需第三方现成 smx，规避「他人信息/不可读/兼容性未知」风险（参考 project_memory 经验教训）。
- 安装/启停基础设施齐全：`l4d2-webctl set-server-plugin-state <id> <enabled|disabled>`、`restart-room <room1|room2|all>`、全量 tar 备份模式。

## 插件设计（infected_counter.sp）

功能：每 1 秒统计并向所有客户端用 `PrintHintText` 显示一行：`特感: X   普感: Y`。

实现要点（仅用 SourceMod 核心 native，不依赖 left4dhooks，降低耦合）：
- 特感数量：遍历 1..MaxClients，`IsClientInGame(i) && GetClientTeam(i) == 3 && IsPlayerAlive(i)` 计数（team 3 = Infected）。
- 普感数量：`int ent = -1; while ((ent = FindEntityByClassname(ent, "infected")) != -1) count++;`（"infected" 即普通感染者实体）。
- 用 `CreateTimer(1.0, ..., _, TIMER_REPEAT)` 周期刷新；`PrintHintText` 每次调用会刷新底部提示文字，实现"常驻"效果。
- 提供 `sm_cvar` 风格 ConVar `l4d_infcount_enable`（默认 1）便于运行时开关。
- 中文显示：HintText 支持 UTF-8，源码用中文「特感 / 普感」。

源码（最终以实际写入为准，约 50 行）核心结构：
```sourcepawn
#pragma semicolon 1
#pragma newdecls required
#include <sourcemod>
#include <sdktools>

ConVar g_cvEnable;

public Plugin myinfo = {
    name = "Infected Counter HUD",
    author = "L4D2 Manager",
    description = "Show alive special + common infected count",
    version = "1.0",
    url = ""
};

public void OnPluginStart() {
    g_cvEnable = CreateConVar("l4d_infcount_enable", "1", "Enable infected counter HUD", FCVAR_NONE, true, 0.0, true, 1.0);
    CreateTimer(1.0, Timer_Show, _, TIMER_REPEAT);
}

public Action Timer_Show(Handle timer) {
    if (!g_cvEnable.BoolValue) return Plugin_Continue;
    int si = 0;
    for (int i = 1; i <= MaxClients; i++)
        if (IsClientInGame(i) && GetClientTeam(i) == 3 && IsPlayerAlive(i)) si++;
    int common = 0, ent = -1;
    while ((ent = FindEntityByClassname(ent, "infected")) != -1) common++;
    for (int i = 1; i <= MaxClients; i++)
        if (IsClientInGame(i) && !IsFakeClient(i))
            PrintHintText(i, "特感: %d   普感: %d", si, common);
    return Plugin_Continue;
}
```

## Proposed Changes（执行步骤）

- **步骤 0 — 备份**：操作前 `tar -czf /opt/l4d2/left4dead2/addons/sm_plugins_backup_<时间戳>.tar.gz -C /opt/l4d2/left4dead2/addons sourcemod/plugins sourcemod/configs addons` 目录关键项（或复用现有备份模式，至少备份 `plugins/`）。时间戳用 PowerShell 侧 `Get-Date -Format yyyyMMddHHmmss` 生成后传入，避免 `$(date)` 被 PowerShell 解析（参考经验教训）。
- **步骤 1 — 写源码**：本地写 `infected_counter.sp`，scp 到 `/tmp/infected_counter.sp`。
- **步骤 2 — 编译**：在服务器执行
  `sudo -u steam /opt/l4d2/left4dead2/addons/sourcemod/scripting/spcomp /tmp/infected_counter.sp -o /tmp/infected_counter.smx`，检查返回码与告警。
- **步骤 3 — 安装**：把编译产物拷到 `plugins/`：
  `sudo cp /tmp/infected_counter.smx /opt/l4d2/left4dead2/addons/sourcemod/plugins/ && sudo chown steam:steam .../infected_counter.smx`。
- **步骤 4 — 重启**：`l4d2-webctl restart-room all`（用户已同意立即重启）。
- **步骤 5 — 验证**：见下。
- **步骤 6（可选，需用户额外确认）**：在 `app.py` 的 `SERVER_PLUGIN_DEFS` 增加该插件条目，使其出现在管理面板的开关列表里。本次默认不改面板（除非用户要），因为它不在 wyxls 托管下载链中，面板的启停 move 逻辑仍可通过补 `MANAGED_SERVER_PLUGINS` 支持——本步骤留待用户决定。

## Assumptions & Decisions（用户已确认）

- 呈现方式 → 常驻 HUD 实时刷新（`PrintHintText` 每秒刷新）。
- 来源 → 自写 SourcePawn + 服务器 spcomp 编译。
- 额外插件 → 暂不安装。
- 重启时机 → 可立即重启（沿用此前授权）。
- 假设：team 3 = Infected、普感 classname = "infected" 为 L4D2 标准；若编译告警或运行无显示，回退排查。
- 假设：HintText 在战役/对抗模式均可向人类玩家显示；若与 `l4d_infected_hp` 的提示位置冲突，再评估改用其他显示通道。

## 回滚预案

1. **撤下新插件**：`sudo mv /opt/l4d2/left4dead2/addons/sourcemod/plugins/infected_counter.smx /opt/l4d2/left4dead2/addons/sourcemod/plugins/disabled/ && l4d2-webctl restart-room all`（或直接 `set-server-plugin-state` 若已纳入面板托管）。因是纯新增文件，删除/移走即可完全复原，不影响既有插件。
2. **整体回滚**：解压步骤 0 的备份覆盖 `plugins/`，`chown -R steam:steam`，重启。
3. 运行时临时关闭（不撤插件）：控制台 `l4d_infcount_enable 0`。

## Verification

- `spcomp` 返回码 0，生成 `infected_counter.smx`（非空）。
- `systemctl is-active l4d2 l4d2_2` 均 `active`，端口 27015/27016 监听正常。
- SM 错误日志（`addons/sourcemod/logs/errors_*.log`）重启后无该插件相关新增报错（无 RCON，故以日志验证为准）。
- 由用户进游戏实际确认 HUD 显示「特感: X 普感: Y」且数字随战局变化。
