# Checklist

- [x] 本地 `ssh myubuntu2 "whoami"` 返回管理用户名，`ssh myubuntu2 "sudo -v"` 可提权
- [x] SSH 加固后（禁 root 直登/关闭密码登录）新开终端仍能 `ssh myubuntu2` 回连，无锁死风险
- [x] `ssh myubuntu2 "sudo ufw status"` 显示 `22/tcp`、`27015/udp`、`27016/udp`、`8080/tcp` 均 ALLOW；公网 `8080/tcp` 与 A2S `27015/udp`/`27016/udp` 已验证可达
- [x] 主机名、时区、系统更新已完成；`/etc/hosts` Steam CDN（必要时强制 IPv4/代理）已配置；mihomo 已由 systemd 管理，TUN 因 fake-ip 超时临时关闭
- [x] L4D2 已安装到 `/opt/l4d2`，由非 root 用户 `steam` 运行
- [x] `l4d2.service` 与 `l4d2_2.service` 均 active(running)，`27015/udp` 与 `27016/udp` 均在监听
- [x] `server.cfg`/`server_2.cfg` 中 `sv_steamgroup` 使用短 groupID，可见性参数（exclusive/lobby）与目标一致
- [x] 已检查迁移文件中的敏感字段；未发现 `rcon_password`/GSLT，且未写入仓库或聊天记录
- [x] A2S 查询或 `connect SERVER_IP:27015`/`:27016` 直连可达，公网 A2S 已返回 Room 1/Room 2 信息，仍建议用户进入游戏做整体功能验收
- [x] Web 管理面板已部署到 `myubuntu2`：`l4d2-manager-web.service` enabled/active，`8080/tcp` 监听，API 与 Phase3 验证通过，公网登录页可达，真实登录密码仅保存在 `/etc/l4d2-manager-web.env`
- [x] 地图搜索/安装默认使用 `L4D2_DOWNLOAD_PROXY=http://127.0.0.1:7890`：面板与 helper 已部署，mihomo 已更新可用订阅并禁用全局 TUN，仅保留本机代理端口；Steam API 代理探测、Web catalog 搜索、helper Workshop 详情解析均通过
- [x] 新服务器 SourceMod/MetaMod 插件栈已补齐：Web `/api/state` 显示 `metamod=true`、`sourcemod=true`，并扫描到启用/禁用 `.smx` 插件列表
