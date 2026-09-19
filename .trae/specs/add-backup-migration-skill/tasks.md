# Tasks

- [x] Task 1: 创建 `skills/l4d2-backup-migrate/SKILL.md`：编写服务器完整状态备份与迁移 skill。
  - [x] SubTask 1.1: frontmatter（name=`l4d2-backup-migrate`，description 精准描述触发场景：服务器到期/换机的完整状态备份与新机还原，并说明与 server-setup/map/plugin/web-panel 的边界）。
  - [x] SubTask 1.2: 迁移清单章节——A 类「完整迁移」9 项 + B 类「仅保留 ID」2 项，逐项给出服务器路径与说明。
  - [x] SubTask 1.3: 备份流程章节——在旧服务器收集 A 类状态、生成地图 ID 清单、拉取到本地结构化目录的命令（PowerShell→ssh 链路注意事项：时间戳本地生成、base64/单引号规避括号转义）。
  - [x] SubTask 1.4: 新机还原流程章节——按依赖顺序（基础接入→放置配置/脚本/unit→还原插件栈→重编译自写插件→还原白名单/网络加速→按 ID 重新下地图→验证）。
  - [x] SubTask 1.5: 安全规范 + 验证/自检小节（敏感文件占位符、还原后只读健康检查）。
- [x] Task 2: 更新 `skills/l4d2-manager/SKILL.md` 索引：子 skill 导航表新增 `l4d2-backup-migrate` 行。
- [x] Task 3: 更新 `AGENTS.md`：skill 路由列表新增 `l4d2-backup-migrate` 职责描述。
- [x] Task 4: 同步新 skill 到全局目录 `c:\Users\WuHaotian\.trae-cn\skills\l4d2-backup-migrate\SKILL.md`（仅新增文件）。
- [x] Task 5: 迁移能力静态自检——交叉核对备份清单覆盖其它 skill 全部关键状态，且还原步骤逐项消费备份产物，无遗漏。（子代理静态核查 A-E 全 PASS；据反馈补强 4 处一致性：VPK 禁用态 addons_disabled/ 纳入 A6 备份+还原、Clash 代理/l4d2-add-map/框架本体取舍显式说明、目录注释对齐。）

# Task Dependencies
- Task 2 / Task 3 / Task 4 depend on Task 1
- Task 5 depends on Task 1, Task 2, Task 3
