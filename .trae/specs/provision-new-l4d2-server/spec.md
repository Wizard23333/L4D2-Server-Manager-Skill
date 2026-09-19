# 新服务器搭建与迁移 Spec

## Why
当前 L4D2 服务器即将到期，已购买新服务器。需要在新机器上从零完成接入、L4D2 服务初始化，并迁移必要的关键信息（Steam 组 ID、RCON 密码、GSLT 等），使新服务器达到与现状一致的可玩状态（Room1 27015 + Room2 27016），随后由用户进入游戏验收整体功能。

## What Changes
- 指导用户在新服务器上完成首次接入：管理用户、SSH 公钥登录、本地 SSH 别名 `myubuntu`、SSH 加固。
- 配置云安全组与系统防火墙（UFW），放行 `22/tcp`、`27015/udp`、`27016/udp`、`8080/tcp`（Web 面板预留）。
- 完成基础系统校准（主机名、时区、系统更新）与 Steam 网络优化（/etc/hosts CDN、必要时代理 / 强制 IPv4）。
- 在 `/opt/l4d2` 下以非 root 用户 `steam` 安装并运行 L4D2 专用服务器，配置两个房间的启动脚本与 systemd 服务（`l4d2.service` / `l4d2_2.service`）。
- 从仍可访问的旧服务器迁移关键信息：Steam 组 ID（短 groupID）、`rcon_password`、可见性参数、GSLT（如有）。敏感值仅落在新服务器配置或用户私有环境，不写入仓库或聊天记录。
- 完成基础验收（服务运行、端口监听、A2S/直连可达、Steam 组可见性参数正确），交付用户进入游戏做整体功能验收。

## Impact
- Affected specs: `l4d2-server-setup`（首次接入、防火墙、systemd、多房间、可见性、GSLT）；`l4d2-web-panel`（仅预留 8080 端口，本次不部署面板）；`l4d2-backup-migrate`（迁移思路参考）。
- Affected code: 新服务器上的 `/opt/l4d2/start_l4d2.sh`、`start_l4d2_2.sh`、`server.cfg`、`server_2.cfg`、systemd unit、`/etc/hosts`、`/etc/gai.conf`、`~/.ssh/config`（本地）；本仓库不产生代码变更。

## 约束与前置
- 第 1 步新服务器尚未配置 SSH，需要先由用户在云控制台/初始密码登录下手动执行；助手提供逐步指导，验证“新登录方式可用后再关闭旧方式”。
- 迁移来源：旧服务器仍可访问，可直接读取旧 `server*.cfg`、启动脚本等再迁移。
- 安全规范：不暴露真实 `rcon_password`、GSLT、Steam token、SSH 私钥、代理订阅；展示输出前用占位符替换（如 `YOUR_RCON_PASSWORD`、`YOUR_GSLT_TOKEN`）。
- 变更前确认目标房间、重启影响、是否有人在线；优先只读健康检查。

## ADDED Requirements

### Requirement: 新服务器安全接入
The system SHALL 使新服务器具备稳定的、可被助手通过 SSH 别名 `myubuntu` 远程操作的安全接入能力。

#### Scenario: 公钥免密登录可用
- **WHEN** 用户按指导完成管理用户创建、公钥写入 `authorized_keys`、本地 `~/.ssh/config` 配置别名 `myubuntu`
- **THEN** 在本地执行 `ssh myubuntu "whoami"` 返回管理用户名，且 `ssh myubuntu "sudo -v"` 可提权

#### Scenario: SSH 加固后仍可回连
- **WHEN** 在确认公钥登录可用后收紧 SSH 策略（禁 root 直登、关闭密码登录）
- **THEN** 新开终端 `ssh myubuntu` 仍能成功登录，旧方式关闭不导致锁死

### Requirement: 防火墙与端口放行
The system SHALL 在云安全组与系统 UFW 两层放行所需端口。

#### Scenario: 端口放行核对
- **WHEN** 完成放行后执行 `ssh myubuntu "sudo ufw status"`
- **THEN** 显示 `22/tcp`、`27015/udp`、`27016/udp`、`8080/tcp` 均为 ALLOW，且云控制台安全组同样放行

### Requirement: L4D2 双房间服务初始化
The system SHALL 在 `/opt/l4d2` 以用户 `steam` 安装 L4D2，并以 systemd 运行两个房间。

#### Scenario: 两个房间均正常运行
- **WHEN** 安装完成并启动 `l4d2.service` 与 `l4d2_2.service`
- **THEN** `systemctl status` 两服务均为 active(running)，`ss` 显示 `27015/udp` 与 `27016/udp` 在监听

### Requirement: 关键信息迁移
The system SHALL 从旧服务器迁移 Steam 组 ID、RCON 密码、可见性参数与 GSLT（如有）到新服务器配置。

#### Scenario: 可见性参数正确迁移
- **WHEN** 迁移 `sv_steamgroup` 等参数后重启对应房间
- **THEN** `sv_steamgroup` 使用短 `groupID`（非 groupID64），且 `sv_steamgroup_exclusive`、`sv_allow_lobby_connect_only` 与目标可见性一致

### Requirement: 基础验收
The system SHALL 在交付前完成只读基础验收，剩余整体功能由用户进入游戏验收。

#### Scenario: 直连可达
- **WHEN** 基础验收阶段
- **THEN** 通过 A2S 查询或游戏内 `connect SERVER_IP:27015` / `:27016` 可连接，助手汇总验收结果并提示用户进入游戏验收
