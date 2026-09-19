# Checklist

- [x] `skills/l4d2-backup-migrate/SKILL.md` 存在且 frontmatter 含合法 name/description
- [x] description 能精准区分触发场景（到期/换机备份迁移），与其它 6 个 skill 无职责重叠
- [x] 迁移清单含「完整迁移（A 类）」与「仅保留 ID（B 类）」两部分，地图 VPK 明确归入 B 类并保留 Workshop ID
- [x] A 类清单覆盖：启动脚本、server*.cfg、systemd unit、SourceMod 插件栈（含 disabled 态）、自写 .sp 源码、插件 VPK、管理员 admins.txt、/etc/hosts CDN 块、/etc/gai.conf、Web 面板 env/packages.json
- [x] 备份流程给出本地结构化目录与可执行命令，且规避 PowerShell→ssh 括号/引号转义陷阱
- [x] 还原流程按依赖顺序，且自写插件用 spcomp64 重新编译而非搬二进制
- [x] 还原流程对每个备份产物都有对应落地步骤（无孤儿备份项）
- [x] 敏感信息（rcon/GSLT/env）有占位符与本地私有保存规范，不入库
- [x] `skills/l4d2-manager/SKILL.md` 子 skill 导航表已新增 l4d2-backup-migrate 行
- [x] `AGENTS.md` 已更新为含 l4d2-backup-migrate 的 7-skill 路由
- [x] 全局目录 `c:\Users\WuHaotian\.trae-cn\skills\l4d2-backup-migrate\SKILL.md` 已同步且内容与仓库一致（MD5 双边 MATCH；覆盖通过 .NET File.Copy 完成）
- [x] 未触碰 `deploy/` 下任何代码，未回滚用户的无关改动
