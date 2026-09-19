# Tasks

- [x] Task 1: 创建 `l4d2-server-setup` 子 skill
  - [x] SubTask 1.1: 新建 `skills/l4d2-server-setup/SKILL.md`，写 frontmatter（name/description 聚焦"新服务器接入/环境/systemd/SSH/多房间/GSLT"）
  - [x] SubTask 1.2: 迁移原第 0、1、2、10、15、17 章内容，按逻辑顺序组织，保留所有命令/路径/坑，去重交叉引用

- [x] Task 2: 创建 `l4d2-map-manager` 子 skill
  - [x] SubTask 2.1: 新建 `skills/l4d2-map-manager/SKILL.md`，写 frontmatter（聚焦"地图安装/提取/切图/清理/备份"）
  - [x] SubTask 2.2: 迁移原第 3、4、5、6、7、9、12 章内容，并把"当前已验证常用地图入口"快照片段纳入

- [x] Task 3: 创建 `l4d2-plugin-manager` 子 skill
  - [x] SubTask 3.1: 新建 `skills/l4d2-plugin-manager/SKILL.md`，写 frontmatter（聚焦"VPK Mod / SourceMod 插件 / 自写 spcomp64 编译 / 面板启停"）
  - [x] SubTask 3.2: 迁移原第 13、14 章内容，保留 spcomp64 编译流程、HUD/Timer 陷阱、动态扫描、left4dhooks 保护、插件清单

- [x] Task 4: 创建 `l4d2-troubleshooting` 子 skill
  - [x] SubTask 4.1: 新建 `skills/l4d2-troubleshooting/SKILL.md`，写 frontmatter（聚焦"健康检查/日志/报错/IPv6/客户端下载 FAQ"）
  - [x] SubTask 4.2: 迁移原第 8、11 章内容

- [x] Task 5: 创建 `l4d2-web-panel` 子 skill
  - [x] SubTask 5.1: 新建 `skills/l4d2-web-panel/SKILL.md`，写 frontmatter（聚焦"Web 管理面板部署/边界/安全/验证"）
  - [x] SubTask 5.2: 迁移原"可选附加：L4D2 Web 管理面板"整节内容

- [x] Task 6: 改写 `l4d2-manager` 为索引/路由 skill
  - [x] SubTask 6.1: 更新 frontmatter description 为"总入口/导航"
  - [x] SubTask 6.2: 正文改为：服务器快照表 + 安全规范 + 5 个子 skill 导航表（含各自触发场景）+ 第 16 章常用指令快速参考；删除已迁出的详细正文

- [x] Task 7: 更新仓库元信息并同步到全局目录
  - [x] SubTask 7.1: 更新 `AGENTS.md`，把 skill 引用从单一 `l4d2-manager` 改为新的 6 个 skill 结构与路由说明
  - [x] SubTask 7.2: 把 6 个 skill 目录同步到 `c:\Users\WuHaotian\.trae-cn\skills\`（5 个新子 skill 已同步；旧 `l4d2-manager/SKILL.md` 的覆盖被沙箱 allowlist 阻止，需手动覆盖一次）

# Task Dependencies
- Task 6 依赖 Task 1-5（索引需引用已建好的子 skill）
- Task 7 依赖 Task 1-6（同步需所有 skill 就绪）
- Task 1-5 之间相互独立，可并行
