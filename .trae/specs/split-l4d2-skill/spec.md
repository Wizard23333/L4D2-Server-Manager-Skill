# 拆分 l4d2-manager 为多个聚焦子 skill Spec

## Why

当前 [skills/l4d2-manager/SKILL.md](file:///d:/workspace/L4D2-Server-Manager-Skill/skills/l4d2-manager/SKILL.md) 约 850 行、17 个章节，把"服务器搭建、地图管理、插件管理、排障、Web 面板"等多个互不相关的关注点塞进一个文件。按 Anthropic Agent Skills 官方推荐的 **Progressive Disclosure（渐进式披露）** 原则，应拆成多个聚焦单一职责的子 skill，使每个 skill 的 `description` 触发更精准、加载进上下文的内容更精简。

## What Changes

- 将单个 `l4d2-manager` skill 按职责拆分为 **5 个聚焦子 skill**：
  1. `l4d2-server-setup`：新服务器接入、基础环境（Steam CDN/代理）、systemd 服务、SSH 远程管理、多房间配置、GSLT。
  2. `l4d2-map-manager`：创意工坊地图安装、VPK 提取、默认地图修改、RCON 实时切图、已装地图快速切换、存储清理、本地备份恢复。
  3. `l4d2-plugin-manager`：VPK Mod 管理、SourceMod 插件栈、自写 SourcePawn + spcomp64 编译、面板动态扫描启停。
  4. `l4d2-troubleshooting`：标准健康检查、日志噪声、KeyValues 报错、权限、IPv6/gai.conf、客户端重复下载 FAQ。
  5. `l4d2-web-panel`：Web 管理面板部署、功能边界、安全注意事项、验证。
- 将原 `l4d2-manager` 改造为**索引/路由 skill**：保留服务器快照、安全规范、子 skill 导航表和"常用管理指令汇总"快速参考，正文细节迁出到对应子 skill。
- 同步全部子 skill 与索引 skill 到全局目录 `c:\Users\WuHaotian\.trae-cn\skills\`。
- 更新 [AGENTS.md](file:///d:/workspace/L4D2-Server-Manager-Skill/AGENTS.md) 的 skill 引用，指向新结构。

> 说明：这是**文档/skill 结构重组**，不改动 `deploy/` 下的任何代码。原文 17 章内容仅做迁移、去重与按 skill 归类，不删减实际运维知识。

## Impact

- 受影响 skill 能力：`l4d2-manager`（拆分 + 降级为索引）。
- 受影响文件：
  - 新增：`skills/l4d2-server-setup/SKILL.md`、`skills/l4d2-map-manager/SKILL.md`、`skills/l4d2-plugin-manager/SKILL.md`、`skills/l4d2-troubleshooting/SKILL.md`、`skills/l4d2-web-panel/SKILL.md`。
  - 改写：`skills/l4d2-manager/SKILL.md`（变为索引）。
  - 更新：`AGENTS.md`。
  - 同步：`c:\Users\WuHaotian\.trae-cn\skills\` 下对应 5 个子 skill + 索引 skill。
- 不影响：`deploy/l4d2-manager-web/` 下所有代码（app.py / l4d2-webctl / 插件源码等）。

## 章节归属映射（来源：现 SKILL.md 17 章）

| 现章节 | 去向子 skill |
| --- | --- |
| 0 新服务器首次接入准备 | l4d2-server-setup |
| 1 服务器基础环境配置（CDN/代理） | l4d2-server-setup |
| 2 L4D2 服务安装与运行（systemd） | l4d2-server-setup |
| 10 SSH 远程管理技巧 | l4d2-server-setup |
| 15 多实例（多房间）配置 | l4d2-server-setup |
| 17 GSLT 申请与配置 | l4d2-server-setup |
| 3 安装创意工坊地图 | l4d2-map-manager |
| 4 手动提取 VPK 资源 | l4d2-map-manager |
| 5 修改默认启动地图 | l4d2-map-manager |
| 6 游戏内实时切换地图（RCON） | l4d2-map-manager |
| 7 已安装地图快速切换 | l4d2-map-manager |
| 9 存储管理与旧地图清理 | l4d2-map-manager |
| 12 本地地图备份与应急恢复 | l4d2-map-manager |
| 13 插件与 Mod 管理（VPK addons） | l4d2-plugin-manager |
| 14 SourceMod 服务器插件栈 | l4d2-plugin-manager |
| 8 常见问题排查（健康检查/日志/IPv6） | l4d2-troubleshooting |
| 11 常见问题 FAQ（客户端重复下载） | l4d2-troubleshooting |
| 可选附加：L4D2 Web 管理面板 | l4d2-web-panel |
| 16 常用管理指令汇总 | l4d2-manager（索引，作快速参考） |
| 当前服务器快照 | l4d2-manager（索引，并在相关子 skill 各保留所需片段） |

## ADDED Requirements

### Requirement: 五个聚焦子 skill
系统 SHALL 提供 5 个独立子 skill，每个含合法 YAML frontmatter（`name` + `description`），职责单一且不重叠。

#### Scenario: 用户询问地图安装
- **WHEN** 用户请求安装创意工坊地图或切换地图
- **THEN** `l4d2-map-manager` 的 description 应能精准触发，且其正文包含地图安装/提取/切图/清理/备份全部步骤

#### Scenario: 用户询问插件
- **WHEN** 用户请求安装 SourceMod 插件、自写插件或管理 VPK Mod
- **THEN** `l4d2-plugin-manager` 应被触发，包含 spcomp64 编译流程、L4D2 HUD/Timer 陷阱、面板动态扫描启停

#### Scenario: 子 skill 内容来自原文
- **WHEN** 对比子 skill 与原 SKILL.md 对应章节
- **THEN** 运维知识点（命令、路径、参数、坑）无遗漏，仅做去重与归类

### Requirement: 索引/路由 skill
系统 SHALL 将 `l4d2-manager` 改造为精简索引 skill，包含服务器快照、安全规范、子 skill 导航表与常用指令快速参考。

#### Scenario: 用户泛泛询问"管理 L4D2 服务器"
- **WHEN** 用户给出宽泛的服务器管理意图
- **THEN** `l4d2-manager` 提供概览并指引到正确的子 skill

### Requirement: 全局目录同步
系统 SHALL 把所有新建/改写的 skill 同步到 `c:\Users\WuHaotian\.trae-cn\skills\`。

#### Scenario: 全局可用
- **WHEN** 同步完成
- **THEN** 全局目录存在 6 个 skill 子目录，各含 `SKILL.md`，内容与仓库一致

## MODIFIED Requirements

### Requirement: l4d2-manager skill
原 `l4d2-manager` 作为单一巨型 skill 承载全部 L4D2 运维知识；现修改为**索引/路由 skill**，仅保留概览、安全规范、导航与快速参考，详细操作迁至 5 个子 skill。其 frontmatter description 更新为"L4D2 服务器管理总入口/导航"。

## REMOVED Requirements

无（不删除任何运维知识，仅重组到子 skill；原 `l4d2-manager` 目录保留为索引）。
