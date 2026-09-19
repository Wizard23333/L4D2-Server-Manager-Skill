# Tasks

- [x] Task 1: 新服务器首次接入与 SSH 安全配置（用户在新机手动执行，助手逐步指导）
  - [x] SubTask 1.1: 确认基础信息（公网 IP/域名、系统版本、初始登录方式、云安全组入口）
  - [x] SubTask 1.2: 首次登录并创建/确认可 sudo 的管理用户
  - [x] SubTask 1.3: 配置 SSH 公钥登录（本地生成/复用公钥并写入服务器 authorized_keys）
  - [x] SubTask 1.4: 在本地 `~/.ssh/config` 配置别名 `myubuntu2`（旧 `myubuntu` 保留）并验证 `ssh myubuntu2 "whoami"`
  - [x] SubTask 1.5: 确认公钥登录可用后再收紧 SSH 策略（禁 root 直登、关闭密码登录），并验证回连不锁死

- [x] Task 2: 防火墙与端口放行（云安全组 + 系统 UFW 两层）
  - [x] SubTask 2.1: 云控制台安全组放行 `22/tcp`、`27015/udp`、`27016/udp`、`8080/tcp`（公网 `8080/tcp` 与 A2S `27015/udp`/`27016/udp` 已验证可达）
  - [x] SubTask 2.2: 服务器内 `sudo ufw allow` 放行同样端口并 `sudo ufw status` 核对（UFW 已启用，4 端口均 ALLOW）

- [x] Task 3: 基础系统校准与 Steam 网络优化
  - [x] SubTask 3.1: 设置主机名（l4d2-server）、时区（已 Asia/Shanghai）、执行系统更新
  - [x] SubTask 3.2: 配置 `/etc/hosts` Steam CDN 加速（akamai 内容域名）；已修复 mihomo 配置语法并以 systemd 启动，因当前 TUN/fake-ip 会导致直连超时，已临时关闭 TUN、保留代理端口，`steamcmd` 自检可进入 Steam Console

- [x] Task 4: L4D2 双房间服务安装与运行
  - [x] SubTask 4.1: 创建非 root 用户 `steam`，安装 steamcmd 并下载 L4D2 dedicated server 到 `/opt/l4d2`（Linux 直接 `app_update 222860` 返回 `Invalid platform`；已用 SteamCMD 强制 Windows 平台安装公共内容，并从旧机迁移 Linux runtime）
  - [x] SubTask 4.2: 编写 Room1/Room2 启动脚本（`start_l4d2.sh` 27015 / `start_l4d2_2.sh` 27016，含 `+sv_hibernate_when_empty 0`）
  - [x] SubTask 4.3: 配置并启用 `l4d2.service` 与 `l4d2_2.service`（开机自启、崩溃重启）

- [x] Task 5: 从旧服务器迁移关键信息
  - [x] SubTask 5.1: 从旧服务器读取 `server.cfg`/`server_2.cfg` 与启动脚本，提取 Steam 组 ID、可见性参数；迁移文件中未发现 `rcon_password`/GSLT 字段
  - [x] SubTask 5.2: 在新服务器写入 `server.cfg`/`server_2.cfg`，确认 `sv_steamgroup` 用短 groupID、可见性参数与目标一致，敏感值不外泄
  - [x] SubTask 5.3: 重启两个房间使配置生效

- [x] Task 6: 基础验收（助手只读核查，剩余由用户进入游戏验收）
  - [x] SubTask 6.1: 核查两服务 active(running)、`27015/udp`/`27016/udp` 监听、UFW 规则
  - [x] SubTask 6.2: A2S 查询或 `connect SERVER_IP:27015`/`:27016` 直连验证，公网 A2S 已返回 Room 1/Room 2 信息，提示用户进入游戏验收

- [x] Task 7: 修复公网连通性验收阻塞项
  - [x] SubTask 7.1: 用户在腾讯云控制台确认云安全组入站放行 `27015/udp`、`27016/udp`（以及需要 Web 面板时的 `8080/tcp`）
  - [x] SubTask 7.2: 重新执行 A2S 查询或客户端 `connect 124.221.76.226:27015`/`:27016` 直连验证（公网 A2S 已通过）
  - [x] SubTask 7.3: 通过后勾选 Task 2.1、Task 6.2 与对应 checklist 项

- [x] Task 8: Web 管理面板部署与验收
  - [x] SubTask 8.1: 在 `myubuntu2` 上确认面板缺失后，从 `deploy/l4d2-manager-web` 安全部署到 `/opt/l4d2-manager-web`
  - [x] SubTask 8.2: 验证 `l4d2-manager-web.service` enabled/active、`8080/tcp` 监听、`/etc/l4d2-manager-web.env` 仅保存在服务器本地
  - [x] SubTask 8.3: 验证 API/Home/Phase3 与公网 `8080/tcp` 登录页可达；真实 Web 登录密码未输出

- [x] Task 9: 地图下载默认走服务器本机代理
  - [x] SubTask 9.1: 在 Web 面板 helper 中为 Workshop/GameMaps 下载和详情查询默认配置 `L4D2_DOWNLOAD_PROXY=http://127.0.0.1:7890`
  - [x] SubTask 9.2: 在 Web 面板服务中为地图搜索接口启用同一默认代理，并在安装脚本中持久化 env 配置
  - [x] SubTask 9.3: 部署到 `myubuntu2` 后验证 mihomo 代理端口、Web 服务、地图搜索/API 与一次安全的下载链路检查（已更新可用订阅并转换为 mihomo 配置；Steam API 代理探测、Web catalog 搜索、helper Workshop 详情解析均通过）

- [x] Task 10: 补齐新服务器 SourceMod/MetaMod 插件栈
  - [x] SubTask 10.1: 对比旧服与新服插件清单，确认新服缺失 `addons/metamod`、`addons/sourcemod`、`addons/metamod.vdf` 与 `cfg/sourcemod`
  - [x] SubTask 10.2: 从旧服迁移 SourceMod/MetaMod 栈到 `myubuntu2`，保留 `.smx` 启用/禁用状态与 32-bit `metamod.vdf`
  - [x] SubTask 10.3: 重启两房间并通过 Web 面板 `/api/state` 动态扫描确认 MetaMod/SourceMod 与插件列表可见

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 3
- Task 5 depends on Task 4
- Task 6 depends on Task 5
- Task 7 depends on Task 6
- Task 8 depends on Task 2
- Task 9 depends on Task 8
- Task 10 depends on Task 8
