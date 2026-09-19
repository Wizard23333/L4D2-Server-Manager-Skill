# L4D2 服务器完整状态备份与迁移 Skill Spec

## Why

服务器租期到期或需要更换机器时，目前没有一个统一入口来「把一台 L4D2 服务器的完整运行状态保存到本地，再在新机器上还原」。现有能力是碎片化的：`l4d2-map-manager` 只讲本地地图 VPK 备份，`l4d2-web-panel` 的 Transfer 只导出地图/Mod 的 Workshop ID。配置文件、SourceMod 插件栈（含自写 `.smx`/`.sp`）、管理员白名单、网络加速（hosts/gai.conf）、Web 面板配置等关键状态没有被纳入任何「整机迁移」清单，换服务器时极易遗漏。

## What Changes

- 新增一个**独立** skill `l4d2-backup-migrate`，作为「服务器完整状态备份 + 新机迁移还原」的单一职责入口。
  - 理由：备份/迁移是横跨 setup/map/plugin/web-panel 四个领域的横切能力，塞进任一现有 skill 都会破坏其单一职责；独立 skill 更符合 Progressive Disclosure，触发场景（到期迁移）也清晰独立。
- 定义一份**迁移清单（Migration Manifest）**：明确「必须完整迁移的小体积状态」与「只保留 ID、到新机重新下载的大体积资源（地图 VPK）」两类。
- 给出**备份流程**：在旧服务器上把需要的状态打包并拉取到本地（含目录结构与命令）。
- 给出**新机还原流程**：按依赖顺序在新服务器上重建状态，地图按保留的 Workshop ID 重新下载。
- 更新 `l4d2-manager` 索引：子 skill 导航表新增 `l4d2-backup-migrate` 一行。
- 更新 `AGENTS.md`：路由结构从 6 skill 增至 7 skill。
- 同步新 skill 到全局目录 `c:\Users\WuHaotian\.trae-cn\skills\`（仅新增文件，允许）。

无破坏性变更：不修改任何现有 skill 的既有内容，只在 `l4d2-manager` 导航表与 `AGENTS.md` 追加引用。

## Impact

- Affected specs / capabilities：新增 `l4d2-backup-migrate`；`l4d2-manager`（索引导航表）。
- Affected code / 文件：
  - 新增 `skills/l4d2-backup-migrate/SKILL.md`
  - 修改 `skills/l4d2-manager/SKILL.md`（子 skill 导航表 + 必要的快照备注）
  - 修改 `AGENTS.md`（skill 路由列表）
  - 同步 `c:\Users\WuHaotian\.trae-cn\skills\l4d2-backup-migrate\SKILL.md`
- 不触碰 `deploy/` 下任何代码。

## 需要纳入备份的服务器状态（清单设计依据）

> 依据现有各 skill 已记录的运行形态梳理。

**A. 完整迁移（小体积，必须原样还原）：**
1. 启动脚本：`/opt/l4d2/start_l4d2.sh`、`/opt/l4d2/start_l4d2_2.sh`（含 `+map`、`+hostport`、`+sv_hibernate_when_empty` 等参数；含 GSLT/rcon 等敏感值，迁移时本地加密保存、不入库）。
2. 房间配置：`/opt/l4d2/left4dead2/cfg/server.cfg`、`server_2.cfg`（含 `sv_steamgroup`、可见性、`rcon_password`）。
3. systemd unit：`l4d2.service`、`l4d2_2.service`。
4. SourceMod 插件栈：`addons/sourcemod/plugins/`（启用）、`addons/sourcemod/plugins/disabled/`（禁用态本身也是状态）、`addons/sourcemod/configs/`、`cfg/sourcemod/`。
5. 自写插件源码：仓库 `deploy/l4d2-manager-web/plugins/*.sp`（随仓库走，新机用 `spcomp64` 重新编译，避免直接搬二进制）。
6. 插件类 VPK：`left4bots2.vpk`、`left4lib.vpk`、`admin_system.vpk`（体积相对小，建议直接迁移；也记录其 Workshop ID 作为兜底重新下载）。
7. 管理员白名单：`ems/left4bots/cfg/admins.txt`、`ems/admin system/admins.txt`（含 SteamID）。
8. 网络加速：`/etc/hosts` 的 `L4D2-STEAM-CDN` 块、`/etc/gai.conf` 的 `precedence ::ffff:0:0/96 100` 行。
9. Web 面板状态（如启用）：`/etc/l4d2-manager-web.env`（敏感）、`/var/lib/l4d2-manager-web/packages.json`（地图来源/ID 记录）。

**B. 只保留 ID、到新机重新下载（大体积）：**
1. 地图 VPK 与已提取资源（`addons/*.vpk` 中的地图包、`left4dead2/maps/*.bsp` 等）—— 只保留 Workshop ID / 来源记录（优先取 `packages.json`），新机用 `l4d2-add-map` / Web 面板按 ID 重新安装。
2. SteamCMD workshop 缓存 —— 不迁移。

## ADDED Requirements

### Requirement: 服务器完整状态备份
该 skill SHALL 提供从运行中的旧服务器把「完整迁移类」状态收集并拉取到本地的流程，且 SHALL 将地图等大体积资源降级为「仅保留 ID」记录。

#### Scenario: 旧服务器到期前导出
- **WHEN** 用户在旧服务器到期前执行备份流程
- **THEN** 本地得到一个结构化备份目录，含全部 A 类状态文件（配置/插件/权限/网络加速/面板配置）、一份地图 Workshop ID 清单，以及一份还原说明索引
- **AND** 大体积地图 VPK 不被打包，仅以 ID/来源形式记录

#### Scenario: 敏感信息处理
- **WHEN** 备份内容包含 `rcon_password` / GSLT / Web 登录 env 等敏感值
- **THEN** skill SHALL 要求这些文件只保存在本地私有路径，不写入仓库、Issue、提交说明或聊天记录，并在文档示例中用占位符

### Requirement: 新服务器还原部署
该 skill SHALL 提供在一台全新服务器上按依赖顺序还原服务器状态的流程，地图按保留的 ID 重新下载。

#### Scenario: 新机还原
- **WHEN** 用户在新服务器（已完成 `l4d2-server-setup` 基础接入与 L4D2 安装）上执行还原流程
- **THEN** 配置/启动脚本/systemd/插件栈/管理员白名单/网络加速被还原，两个房间可启动
- **AND** 自写插件用 `spcomp64` 在新机重新编译而非直接搬运二进制
- **AND** 地图按保留的 Workshop ID 用 `l4d2-add-map` 或 Web 面板重新安装

### Requirement: 迁移能力静态自检
由于当前无新服务器可实测，该 skill 与本次交付 SHALL 提供一份静态自检：交叉核对「备份清单」是否覆盖其它 skill 中记录的全部关键状态，且「还原步骤」能逐项消费备份产物。

#### Scenario: 完整性交叉核对
- **WHEN** 对照 `l4d2-server-setup` / `l4d2-map-manager` / `l4d2-plugin-manager` / `l4d2-web-panel` 中记录的状态项
- **THEN** 每个关键状态项要么出现在「完整迁移」清单，要么在「仅保留 ID」清单中有明确理由，无遗漏
- **AND** 还原流程对每个备份产物都有对应的落地步骤

## MODIFIED Requirements

### Requirement: l4d2-manager 作为索引/路由
`l4d2-manager` 的子 skill 导航表 SHALL 增加 `l4d2-backup-migrate` 行，触发场景描述为「服务器到期/换机时的完整状态备份与新机迁移还原」。其余索引内容保持不变。

## REMOVED Requirements

无。
