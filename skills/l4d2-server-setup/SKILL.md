---
name: "l4d2-server-setup"
description: "L4D2 专用服务器的接入与运行基础。当需要从零接入新 Ubuntu/Debian 服务器、做 SSH 加固与防火墙放行、配置 Steam CDN/代理、安装并运行 systemd 游戏服务、配置多房间（多实例）、设置房间公开/私密可见性，或申请配置 GSLT 时调用。不负责地图、插件或 Web 面板的具体操作。"
---

# L4D2 服务器接入、环境与运行基础

本 skill 覆盖 L4D2 专用服务器的「从零接入 -> 基础环境 -> systemd 运行 -> SSH 远程管理 -> 多房间 -> 可见性 -> GSLT」全链路。地图管理见 `l4d2-map-manager`，插件见 `l4d2-plugin-manager`，排障见 `l4d2-troubleshooting`，Web 面板见 `l4d2-web-panel`。

## 当前服务器快照

> 更新时间：2026-10-10，由当前生产机 `myubuntu2`（主机名 `l4d2-server`）只读核验。记录运行形态，不记录真实 RCON 密码、GSLT、Steam token 等敏感信息。

| 房间 | 服务 | 端口 | 配置文件 | 默认地图 | 可见性 |
| --- | --- | --- | --- | --- | --- |
| Room 1 | `l4d2.service` | `27015/udp` | `server.cfg` | `l4d2_bts01_forest` | Steam 组内专属（`sv_steamgroup_exclusive 1`） |
| Room 2 | `l4d2_2.service` | `27016/udp` | `server_2.cfg` | `glubtastic5_1` | 公开可搜（`sv_steamgroup_exclusive 0`） |

- 两房间同属 Steam 组 `46097240`；`sv_lan 0`、`sv_region 4`；均未设 `sv_password`。
- 安装目录：`/opt/l4d2`，所有服务由非 root 用户 `steam` 运行。
- 本地 SSH 别名：`myubuntu2`（后文命令大量使用）。

## 安全与敏感信息规范（始终遵守）

以下内容只允许保存在服务器配置或本机私有环境，不要写入公开文档、Issue、提交说明或聊天记录：
- `rcon_password` 的真实值。
- `+sv_setsteamaccount` 后面的 GSLT。
- Steam API、代理订阅、SSH 私钥、服务器登录凭据。

展示命令输出前，尤其是 `systemctl status`、`systemctl cat`、`start_l4d2*.sh`、`server*.cfg`，需要先把 token 和密码替换成占位符，例如 `YOUR_RCON_PASSWORD`、`YOUR_GSLT_TOKEN`。

变更前确认：目标房间、重启影响范围、当前是否有人在线；优先做只读健康检查再改状态。

---

## 1. 新服务器首次接入前必须手动完成的准备

如果你刚拿到一台新的 Ubuntu / Debian 服务器，下面这些步骤建议先由你手动完成，再继续后续地图、服务和 Web 面板相关操作。这一章只覆盖“首次接入与安全基线”，不代替完整的系统加固文档；所有真实密码、私钥、token 只保存在服务器配置或你自己的私有环境中。

### A. 确认服务器基础信息
在开始登录前，先把以下信息确认好并单独保存：
- 公网 IP 或可用域名，例如 `YOUR_SERVER_IP`。
- 系统版本是否为 Ubuntu / Debian，便于后续使用 `apt`、`systemd` 和 `ufw`。
- 云厂商提供的初始登录方式：密码、控制台注入公钥、救援模式或 VNC。
- 云控制台里是否能看到安全组 / 防火墙规则入口。

如果这些基础信息都不明确，后续做 SSH 加固和防火墙放行时很容易把自己锁在服务器外。

### B. 完成首次登录
首次登录可以先使用云厂商提供的初始密码，或使用镜像预置的登录账号：

```bash
ssh root@YOUR_SERVER_IP
```

或者：

```bash
ssh ubuntu@YOUR_SERVER_IP
```

注意事项：
- 首次登录阶段不要急着关闭密码登录或禁止 root 登录。
- 先确认你可以稳定连上，并且知道当前系统给你的默认账号是什么。
- 如果云厂商要求你先在控制台重置密码，请先完成这一步。

### C. 创建或确认可用的管理账号
后续日常管理建议使用一个可 `sudo` 的普通用户，而不是长期直接使用 `root`。

如果云镜像已经自带管理用户（例如 `ubuntu`），先确认它可用：

```bash
whoami
sudo -v
```

如果没有现成的管理用户，再手动创建一个：

```bash
sudo adduser YOUR_SSH_USER
sudo usermod -aG sudo YOUR_SSH_USER
```

完成后建议重新开一个终端测试该用户是否能登录和提权，确认没问题再继续下一步。

### D. 配置 SSH 公钥登录
先在本地电脑确认你已有可用公钥；如果没有，可以在本地终端生成：

```bash
ssh-keygen -t ed25519 -C "l4d2-admin"
```

然后把本地公钥追加到服务器目标用户的 `authorized_keys`。例如把本地 `~/.ssh/id_ed25519.pub` 的内容复制到服务器：

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

保存后，从本地新开一个终端验证是否能免密登录：

```bash
ssh YOUR_SSH_USER@YOUR_SERVER_IP
```

只有在这一步验证成功之后，才建议继续收紧 SSH 策略。

### E. 在本地配置 SSH 别名
为了和本文档后续命令保持一致，建议你在本地 `~/.ssh/config` 中提前配置一个固定别名，例如 `myubuntu2`：

```sshconfig
Host myubuntu2
    HostName YOUR_SERVER_IP
    User YOUR_SSH_USER
    IdentityFile ~/.ssh/id_ed25519
```

完成后测试：

```bash
ssh myubuntu2 "whoami"
```

后文大量命令都默认使用这种形式，例如 `ssh myubuntu2 "sudo systemctl status l4d2"`。

### F. 加固 SSH 登录策略
在确认“公钥登录 + sudo 用户 + 本地 SSH 别名”都正常后，再考虑收紧 SSH 登录策略，例如：
- 禁止 `root` 直接 SSH 登录。
- 关闭基于密码的 SSH 登录，仅保留公钥。
- 明确记录 SSH 端口是否保持默认 `22/tcp`。

这一步的核心原则是：**先验证新登录方式可用，再去关闭旧方式**。不要在只开着一个 root 会话、且还没验证公钥回连时就直接改 SSH 策略。

### G. 配置云安全组与系统防火墙
这一步也必须按顺序来做。

先保证 SSH 所需端口已放行：
- 云厂商安全组 / 防火墙中放行 `22/tcp`。
- 服务器内如果启用了 `ufw`，也要放行 `22/tcp`。

常用命令示例：

```bash
sudo ufw allow 22/tcp
sudo ufw status
```

随后再根据实际用途逐步放行其他端口：
- `27015/udp`：Room 1 游戏端口。
- `27016/udp`：Room 2 游戏端口。
- `8080/tcp`：仅当你要启用 Web 管理面板时才需要放行。

建议把“云安全组”和“服务器内防火墙”当成两层规则分别检查，缺一不可。例如：

```bash
sudo ufw allow 27015/udp
sudo ufw allow 27016/udp
```

如果暂时还不用 Web 面板，可以先不要开放 `8080/tcp`。

### H. 执行基础系统校准
在进入 L4D2 安装前，建议先做几项基础校准：
- 设置正确的主机名，便于区分多台服务器。
- 设置时区，确保后续 `journalctl` 与日志时间可读。
- 执行一次基础系统更新，避免刚装机时包索引过旧。

常用命令示例：

```bash
sudo hostnamectl set-hostname l4d2-server
sudo timedatectl set-timezone Asia/Shanghai
sudo apt update && sudo apt upgrade -y
```

### I. 做一轮接入验证
在开始后续步骤之前，建议你至少完成下面这轮人工验证：
1. 从本地用 `ssh myubuntu2` 重新连接一次，确认不是靠旧会话“假在线”。
2. 执行 `sudo -v`，确认管理用户有提权能力。
3. 执行 `sudo ufw status`，确认当前放行规则符合你的预期。
4. 在云控制台再次检查安全组，确认 `22/tcp` 和需要的游戏端口已放行。
5. 确认此时即使断开当前 SSH 窗口，你也能重新连接回来。

---

## 2. 服务器基础环境配置

在安装游戏之前，为了解决国内服务器访问 Steam 网络慢、下载失败的问题，执行了以下核心配置：

### A. Steam CDN 节点优化 (Hosts)
通过修改 `/etc/hosts` 将 Steam 创意工坊和资源域名强制指向高速 CDN 节点（如香港节点），解决了下载速度只有几 KB 的问题。
- **关键域名**：`cloud-3.steamusercontent.com`, `steamcommunity-a.akamaihd.net` 等。
- **生效验证**：使用 `ping` 确认指向了 23.67.33.221 (Akamai)。

### B. 网络代理配置 (Clash + Proxychains)
为了让 `steamcmd` 能够稳定连接 Steam 服务器，配置了临时代理：
- **Clash (mihomo)**：部署在服务器上，通过订阅链接获取节点，提供 SOCKS5 代理。
- **Proxychains4**：用于将 `steamcmd` 的流量强制转发至 Clash 代理。配置位于 `/tmp/proxychains_l4d2.conf`。

> IPv6 出网不可达导致 steamcmd / 下载超时的处理（强制 IPv4 / gai.conf），见 `l4d2-troubleshooting`。

---

## 3. L4D2 服务安装与运行

### A. 安装目录
- **路径**：`/opt/l4d2`
- **用户**：`steam` (为了安全，所有服务由该非 root 用户运行)

### B. 启动脚本 (`start_l4d2.sh`)
位于 `/opt/l4d2/start_l4d2.sh`，定义了核心启动参数：
- `+ip 0.0.0.0`: 监听所有网卡。
- `+hostport 27015`: 游戏端口。
- `+map <地图名>`: 默认加载地图。
- `+sv_hibernate_when_empty 0`: **关键配置**，禁用空闲休眠，确保 RCON 随时可用。

> 修改默认启动地图（`+map`）属于地图管理范畴，见 `l4d2-map-manager`。

### C. 系统服务 (Systemd)
配置了 `l4d2.service`，实现开机自启和崩溃自动重启：
- `sudo systemctl start l4d2` (启动)
- `sudo systemctl restart l4d2` (重启)
- `sudo systemctl status l4d2` (状态)

---

## 4. 服务器远程管理技巧 (SSH)

为了方便管理，在本地配置了 SSH 别名，无需记忆复杂的 IP 地址。

### A. SSH 别名配置 (本地)
在本地终端执行命令时，使用 `myubuntu2` 即可连接服务器：
- **别名**：`myubuntu2`
- **配置文件**：`~/.ssh/config` (本地)
- **使用示例**：
  ```bash
  ssh myubuntu2 "sudo systemctl status l4d2"
  ```

### B. 远程执行命令常用模式
- **查看实时日志**：
  ```bash
  ssh myubuntu2 "sudo journalctl -u l4d2.service -f"
  ```
- **重启游戏服务**：
  ```bash
  ssh myubuntu2 "sudo systemctl restart l4d2"
  ```

### C. 常用管理指令汇总
- **查看服务状态**：`ssh myubuntu2 "sudo systemctl status l4d2"` (Room 1) 或 `l4d2_2` (Room 2)
- **重启服务**：`ssh myubuntu2 "sudo systemctl restart l4d2"`
- **查看实时日志**：`ssh myubuntu2 "sudo journalctl -u l4d2.service -f"`
- **查看端口监听**：`ssh myubuntu2 "sudo ss -H -lunp 'sport = :27015'"` 或 `27016`
- **查看最近错误**：`ssh myubuntu2 "sudo journalctl -u l4d2 -u l4d2_2 --since '24 hours ago' --no-pager | grep -Ei 'error|fail|warning|missing|keyvalues' | tail -80"`

---

## 5. 多实例（多房间）配置指南

为了让更多朋友同时玩，可以在同一台服务器上运行多个 L4D2 实例。

### A. 核心配置逻辑
- **端口隔离**：每个房间必须使用唯一的端口（例如 27015, 27016）。
- **防火墙放行**：除了在云服务商控制台开启端口外，还必须在服务器系统内部放行 UDP 端口。
  ```bash
  sudo ufw allow 27016/udp
  ```
- **脚本隔离**：每个房间拥有独立的启动脚本（指定不同的端口和默认地图）。
- **服务隔离**：每个房间配置独立的 Systemd 服务。

### B. 当前房间配置详情

Room 1：
- **服务**：`l4d2.service`
- **端口**：`27015`
- **配置文件**：`server.cfg`
- **默认地图**：`l4d2_bts01_forest`（Back To School 第 1 章）
- **启动脚本**：`/opt/l4d2/start_l4d2.sh`

Room 2：
- **服务**：`l4d2_2.service`
- **端口**：`27016`
- **配置文件**：`server_2.cfg`
- **默认地图**：`glubtastic5_1`
- **启动脚本**：`/opt/l4d2/start_l4d2_2.sh`

### C. 管理指令
- **启动/重启房间 2**：
  ```bash
  ssh myubuntu2 "sudo systemctl restart l4d2_2"
  ```
- **查看房间 2 状态**：
  ```bash
  ssh myubuntu2 "sudo systemctl status l4d2_2"
  ```
- **查看房间 2 日志**：
  ```bash
  ssh myubuntu2 "sudo journalctl -u l4d2_2.service -f"
  ```

### D. 房间曝光与可见性管理 (公开/私密切换)
如果您希望路人玩家能从“匹配模式”或“寻找房间”列表中搜到您的服务器，请确保以下参数：

**1. 公开模式（路人可搜）：**
修改 `server.cfg` 或 `server_2.cfg`：
```hlsl
sv_steamgroup_exclusive 0      // 允许非 Steam 组成员进入
sv_allow_lobby_connect_only 0  // 允许直接从列表/匹配加入
sv_region 4                    // 设置为亚洲区 (4)，国内玩家搜得更快
```

**2. 私密/组内模式（仅限朋友）：**
```hlsl
sv_steamgroup "46097240"       // 使用短 groupID，不要直接填 groupID64
sv_steamgroup_exclusive 1      // 仅限 Steam 成员
sv_allow_lobby_connect_only 1  // 必须通过大厅组队才能进入
```

**Steam 组 ID 易错点：**
- L4D2 的 `sv_steamgroup` 在实际验证中需要使用 Steam 组的短 `groupID`，不要直接填 XML 里的 `groupID64`。
- 如果只有 `groupID64`，可用公式换算短 ID：`groupID = groupID64 - 103582791429521408`。
- 例：`https://steamcommunity.com/groups/l4d2wht` 的 `groupID64` 是 `103582791475618648`，L4D2 `sv_steamgroup` 应填写 `46097240`。
- 修改后重启房间，并用游戏客户端重启 Steam/L4D2 后再看 Steam 组服务器列表。列表刷新有延迟，先用 `connect SERVER_IP:27015` 验证直连。

**修改后必须重启对应房间的服务生效。**

---

## 6. 申请与配置 GSLT 注意事项

**GSLT (Game Server Login Token)** 可以让部分 Source/Steam 服务器获得持久身份，但不要把它和 L4D2 的 Steam 组可见性混为一谈。实际排障中，Steam 组服务器看不到的关键问题是 `sv_steamgroup` 使用了 `groupID64`，改为短 `groupID` 后恢复正常。

### A. 申请步骤
1. 访问 [Steam 游戏服务器账户管理](https://steamcommunity.com/dev/managegameservers)。
2. AppID 填写 `550`。
3. 生成并复制令牌。

### B. 配置方法
如需测试 GSLT，先把 token 保存到服务器私有 env 文件，不要写入仓库或聊天记录。当前 Linux L4D2 dedicated server 环境中，启动参数 `+sv_setsteamaccount YOUR_GSLT_TOKEN` 曾返回 `Unknown command "sv_setsteamaccount"`，因此不要把它作为 Steam 组可见性的主修复手段。

排障优先级：
1. 确认 `sv_steamgroup` 使用短 `groupID`。
2. 确认 `sv_steamgroup_exclusive` 和 `sv_allow_lobby_connect_only` 符合目标可见性。
3. 确认 `27015/udp`、`27016/udp` 在云安全组和 UFW 都已放行。
4. 用 A2S 查询或游戏内 `connect SERVER_IP:PORT` 先验证直连。
5. 再考虑 GSLT、Steam master 列表延迟或客户端 Steam 组列表缓存。
