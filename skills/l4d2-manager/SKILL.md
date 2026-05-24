---
name: "l4d2-manager"
description: "管理 L4D2 服务器配置、地图安装及实时切换。当需要安装地图、修改启动参数或通过 RCON 切换地图时调用。"
---

# L4D2 服务器基础配置与地图管理指南

本指南记录了从零开始配置 L4D2 专用服务器的全过程，包括环境优化、代理设置、基础安装以及后续的地图管理。

---

## 当前服务器快照

> 更新时间：2026-05-02。记录运行形态和排障入口，不记录真实 RCON 密码、GSLT、Steam token 等敏感信息。

| 房间 | 服务 | 端口 | 配置文件 | 默认地图 | 可见性 |
| --- | --- | --- | --- | --- | --- |
| Room 1 | `l4d2.service` | `27015/udp` | `server.cfg` | `hls_05` | Steam 组内/私密 |
| Room 2 | `l4d2_2.service` | `27016/udp` | `server_2.cfg` | `zc_m1` | 公开可搜 |

当前已安装的主要 VPK：
- 地图：`gzzc7.3.vpk`（广州增城）、`tianti.vpk`（天梯）。
- 插件：`left4bots2.vpk`、`left4lib.vpk`、`admin_system.vpk`。

当前已验证的常用自定义地图入口：
- `zc_m1` 至 `zc_m5`：广州增城。
- `hls_05`：天梯 / Ladder to Heaven。
- `dxyl1` 至 `dxyl4_f`：地心引力。
- `l4d_yama_1` 至 `l4d_yama_5`：Yama。
- `mtlgth001` 至 `mtlgth005`：MTL Gone To Hell。
- `q_ancienttown`、`q_ancienttown2`、`q_fleshbridge1`、`q_fleshbridge2`、`q_fleshbridgesurvive`：HOME TOWN 相关关卡。

---

## 0. 新服务器首次接入前必须手动完成的准备

如果你刚拿到一台新的 Ubuntu / Debian 服务器，下面这些步骤建议先由你手动完成，再继续执行本 skill 里的地图、服务和 Web 面板相关操作。这一章只覆盖“首次接入与安全基线”，不代替完整的系统加固文档；所有真实密码、私钥、token 只保存在服务器配置或你自己的私有环境中，不要写进公开文档。

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
为了和本文档后续命令保持一致，建议你在本地 `~/.ssh/config` 中提前配置一个固定别名，例如 `myubuntu`：

```sshconfig
Host myubuntu
    HostName YOUR_SERVER_IP
    User YOUR_SSH_USER
    IdentityFile ~/.ssh/id_ed25519
```

完成后测试：

```bash
ssh myubuntu "whoami"
```

后文大量命令都默认使用这种形式，例如 `ssh myubuntu "sudo systemctl status l4d2"`。

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
在开始后续 skill 步骤之前，建议你至少完成下面这轮人工验证：
1. 从本地用 `ssh myubuntu` 重新连接一次，确认不是靠旧会话“假在线”。
2. 执行 `sudo -v`，确认管理用户有提权能力。
3. 执行 `sudo ufw status`，确认当前放行规则符合你的预期。
4. 在云控制台再次检查安全组，确认 `22/tcp` 和需要的游戏端口已放行。
5. 确认此时即使断开当前 SSH 窗口，你也能重新连接回来。

完成以上步骤后，再继续阅读后面的“服务器基础环境配置”“L4D2 服务安装与运行”等章节，会更安全，也更不容易中途失联。

---

## 1. 服务器基础环境配置

在安装游戏之前，为了解决国内服务器访问 Steam 网络慢、下载失败的问题，我们执行了以下核心配置：

### A. Steam CDN 节点优化 (Hosts)
通过修改 `/etc/hosts` 将 Steam 创意工坊和资源域名强制指向高速 CDN 节点（如香港节点），解决了下载速度只有几 KB 的问题。
- **关键域名**：`cloud-3.steamusercontent.com`, `steamcommunity-a.akamaihd.net` 等。
- **生效验证**：使用 `ping` 确认指向了 23.67.33.221 (Akamai)。

### B. 网络代理配置 (Clash + Proxychains)
为了让 `steamcmd` 能够稳定连接 Steam 服务器，配置了临时代理：
- **Clash (mihomo)**：部署在服务器上，通过订阅链接获取节点，提供 SOCKS5 代理。
- **Proxychains4**：用于将 `steamcmd` 的流量强制转发至 Clash 代理。配置位于 `/tmp/proxychains_l4d2.conf`。

---

## 2. L4D2 服务安装与运行

### A. 安装目录
- **路径**：`/opt/l4d2`
- **用户**：`steam` (为了安全，所有服务由该非 root 用户运行)

### B. 启动脚本 (`start_l4d2.sh`)
位于 `/opt/l4d2/start_l4d2.sh`，定义了核心启动参数：
- `+ip 0.0.0.0`: 监听所有网卡。
- `+hostport 27015`: 游戏端口。
- `+map <地图名>`: 默认加载地图。
- `+sv_hibernate_when_empty 0`: **关键配置**，禁用空闲休眠，确保 RCON 随时可用。

### C. 系统服务 (Systemd)
配置了 `l4d2.service`，实现开机自启和崩溃自动重启：
- `sudo systemctl start l4d2` (启动)
- `sudo systemctl restart l4d2` (重启)
- `sudo systemctl status l4d2` (状态)

---

## 3. 安装新的创意工坊地图

**建议优先使用三方地图下载工具**（如 Steam API 或第三方 Web 下载器），以避开 SteamCMD 在国内的连接限制。

- **推荐工具**：使用 `curl` 调用 Steam API 获取直链，并配合 `aria2c` 进行多线程下载。

### A. 自动化脚本方式
使用已配置的自动化脚本 `l4d2-add-map`。该脚本会自动处理代理、下载并拷贝到 `addons` 目录。

注意：当前 `/usr/local/bin/l4d2-add-map` 安装完成后只会自动重启 `l4d2.service`。如果地图或 Mod 也要给 Room 2 使用，需要手动重启 `l4d2_2.service`，或后续把脚本改成支持选择目标房间。

- **执行命令：**
```bash
# 在服务器终端执行
sudo l4d2-add-map <Workshop_ID>
```
*例如：安装地心引力地图*
```bash
sudo l4d2-add-map 3526529688
```

双房间同步后按需重启：
```bash
ssh myubuntu "sudo systemctl restart l4d2"
ssh myubuntu "sudo systemctl restart l4d2_2"
```

### B. 三方下载源 (Steam API 备选方案)
如果 `steamcmd` 速度过慢或挂起，可使用 Steam API 获取直链并用 `aria2c` 下载：
1.  **获取直链**：
    ```bash
    curl -d 'itemcount=1&publishedfileids[0]=<Workshop_ID>' -X POST https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/
    ```
2.  **使用 aria2c 下载**：
    ```bash
    aria2c -x 16 -s 16 -o /tmp/map.vpk '<file_url>'
    ```

---

## 4. 手动提取 VPK 资源 (推荐)

为了服务器稳定性，建议将 VPK 内容直接提取到游戏核心目录。

**步骤：**
1. 使用本地的 `vpk_extract.py` 脚本提取 VPK：
   ```bash
   python3 vpk_extract.py <VPK路径> <目标提取目录>
   ```
2. 将提取出的文件夹（如 `maps`, `missions`, `materials`, `models`, `sound`）同步到服务器的 `/opt/l4d2/left4dead2/` 目录下。

---

## 5. 修改服务器默认启动地图

若需更改服务器启动时加载的地图，需修改启动脚本。

**修改文件：** `/opt/l4d2/start_l4d2.sh`

**操作步骤：**
1. 找到 `+map` 参数。
2. 将其后的地图名改为新地图的第一关名称（例如 `zc_m1`）。
3. 重启服务：
   ```bash
   sudo systemctl restart l4d2
   ```

---

## 6. 游戏内实时切换地图 (RCON)

无需重启服务器，直接在游戏控制台中操作。

**前提：** 确保你已知晓 `rcon_password`（当前为 `YOUR_RCON_PASSWORD`）。

**操作步骤：**
1. 在游戏中按 **`~`** 开启控制台。
2. 认证 RCON 权限：
   ```hlsl
   rcon_password "YOUR_RCON_PASSWORD"
   ```
3. 执行切图命令：
   ```hlsl
   rcon changelevel <地图名>
   ```

---

## 7. 已安装地图的快速切换

如果你已经通过上述步骤下载并安装了多张地图，无需修改启动脚本或重启服务器，可以通过 RCON 远程指令实现秒级切换。

### A. 获取已安装地图列表
在服务器终端执行以下命令，查看当前有哪些可用的地图关卡（`.bsp` 文件）：
```bash
ls /opt/l4d2/left4dead2/maps/*.bsp | xargs -n1 basename | sed 's/\.bsp//'
```

### B. 快速切换流程 (RCON)
1.  **进入游戏**，按 **`~`** 开启控制台。
2.  **获取管理员权限**：
    ```hlsl
    rcon_password "YOUR_RCON_PASSWORD"
    ```
3.  **执行切图命令**：
    ```hlsl
    # 语法：rcon changelevel <地图关卡名>
    rcon changelevel dxyl1    # 切换到地心引力第一关
    rcon changelevel zc_m1    # 切换到广州增城第一关
    rcon changelevel l4d_yama_1 # 切换到 Yama 第一关
    rcon changelevel mtlgth001 # 切换到 MTL Gone To Hell 第一关
    rcon changelevel q_ancienttown # 切换到 HOME TOWN 第一关
    rcon changelevel hls_05    # 切换到 天梯 (Ladder to Heaven) 第一关
    ```

---

## 8. 常见问题排查 (Troubleshooting)

### A. 标准健康检查流程

当需要判断服务器是否正常运行时，先查服务，再查端口，最后看日志：

```bash
ssh myubuntu "sudo systemctl status l4d2 --no-pager"
ssh myubuntu "sudo systemctl status l4d2_2 --no-pager"
ssh myubuntu "sudo systemctl show l4d2 l4d2_2 -p NRestarts -p ExecMainStatus -p ExecMainStartTimestamp --no-pager"
ssh myubuntu "sudo ss -H -lunp 'sport = :27015'"
ssh myubuntu "sudo ss -H -lunp 'sport = :27016'"
```

最近错误快速过滤：
```bash
ssh myubuntu "sudo journalctl -u l4d2 -u l4d2_2 --since '24 hours ago' --no-pager | grep -Ei 'error|fail|warning|missing|denied|recursive|keyvalues|crash|segmentation' | tail -80"
```

判断标准：
- `Active: active (running)` 且 `NRestarts=0`：systemd 层面稳定。
- `ss` 能看到 `srcds_linux` 监听 `27015/udp` 或 `27016/udp`：游戏端口已绑定。
- 日志有自定义模型或脚本报错，但服务未重启：通常优先按地图/Mod 兼容性排查，不要直接判断为服务器崩溃。

### B. 当前已知日志噪声和风险点

Room 2 最近较常见的自定义资源报错：
- `models/tmp_mod/fallout_table1.mdl` 反复出现 `KeyValues Error`。
- 部分模型出现 `Can't create physics object`。
- 曾出现脚本变量缺失：`q_tankhealth1 does not exist`。
- 偶发 `STEAMAUTH failure code 6/8`，通常和客户端 Steam 认证状态或网络有关。

这些错误目前没有导致 `l4d2_2.service` 重启。若玩家反馈某张图卡死、模型异常、进图失败，再结合报错时间点定位对应地图资源。

### C. KeyValues Error (RecursiveLoadFromBuffer)
通常由 `missions/*.txt` 文件引起：
- **原因1：存在 BOM 头。** 修复：`sudo sed -i '1s/^\xef\xbb\xbf//' <文件路径>`
- **原因2：括号不匹配。** 修复：检查文件末尾是否缺失 `}`。

如果错误指向 `.mdl`、`.vtx`、`.phy` 等模型资源，通常不是 `missions/*.txt` 的问题，而是地图或 Mod 自带资源兼容性问题。优先确认对应 VPK 是否完整、是否和客户端版本一致、是否存在多个版本冲突。

### D. 权限问题
若地图无法加载，确保 `steam` 用户拥有文件权限：
```bash
sudo chown -R steam:steam /opt/l4d2/left4dead2/
```

---

## 9. 存储管理与旧地图清理

随着安装的地图增多，服务器磁盘空间可能会被占满。地图文件主要存在于两个位置：

1.  **Addons 目录** (`/opt/l4d2/left4dead2/addons/`): 这里存放着正在使用的 `.vpk` 文件。
2.  **SteamCMD 缓存** (`/home/steam/Steam/steamapps/workshop/content/550/`): 这里存放着下载时的原始文件。

### 当前容量基线

2026-05-02 检查结果：
- 根分区 `/`：40G 总量，约 25G 已用，13G 可用，使用率约 67%。
- `/opt/l4d2/left4dead2/maps`：约 2.4G。
- `/opt/l4d2/left4dead2/addons`：约 884M。
- `/opt/l4d2/left4dead2/downloads`：约 2M。
- `/home/steam/Steam/steamapps/workshop/content/550`：当前未发现明显缓存文件。

容量检查命令：
```bash
ssh myubuntu "df -h /opt/l4d2"
ssh myubuntu "sudo du -sh /opt/l4d2/left4dead2/addons /opt/l4d2/left4dead2/maps /opt/l4d2/left4dead2/missions /opt/l4d2/left4dead2/downloads 2>/dev/null"
```

### 如何清理旧地图：
- **删除 Addons 中的 VPK**: 
  ```bash
  sudo rm /opt/l4d2/left4dead2/addons/旧地图.vpk
  ```
- **清理 SteamCMD 下载缓存 (释放空间)**:
  ```bash
  sudo rm -rf /home/steam/Steam/steamapps/workshop/content/550/*
  ```
- **清理已提取的文件**:
  如果你手动提取了 VPK 内容到 `left4dead2/maps` 等目录，需手动删除对应的 `.bsp` 或文件夹。

---

## 10. 服务器远程管理技巧 (SSH)

为了方便管理，我们在本地配置了 SSH 别名，无需记忆复杂的 IP 地址。

### A. SSH 别名配置 (本地)
在本地终端执行命令时，使用 `myubuntu` 即可连接服务器：
- **别名**：`myubuntu`
- **配置文件**：`~/.ssh/config` (本地)
- **使用示例**：
  ```bash
  ssh myubuntu "sudo systemctl status l4d2"
  ```

### B. 远程执行命令常用模式
- **查看实时日志**：
  ```bash
  ssh myubuntu "sudo journalctl -u l4d2.service -f"
  ```
- **重启游戏服务**：
  ```bash
  ssh myubuntu "sudo systemctl restart l4d2"
  ```

### C. 敏感信息处理规范

以下内容只允许保存在服务器配置或本机私有环境中，不要写入公开文档、Issue、提交说明或聊天记录：
- `rcon_password` 的真实值。
- `+sv_setsteamaccount` 后面的 GSLT。
- Steam API、代理订阅、SSH 私钥、服务器登录凭据。

展示命令输出前，尤其是 `systemctl status`、`systemctl cat`、`start_l4d2*.sh`、`server*.cfg`，需要先把 token 和密码替换成占位符，例如 `YOUR_RCON_PASSWORD`、`YOUR_GSLT_TOKEN`。

---

## 可选附加：L4D2 Web 管理面板

Web 管理面板是部署在服务器上的轻量浏览器界面，适合日常查看房间状态、切换默认地图、搜索安装三方地图和管理 VPK。它是本 skill 的可选附加能力，不是使用 SSH、RCON 和脚本流程的前置条件；不需要网页时，仍可完全按前文命令行流程管理服务器。

部署包位于仓库的 `deploy/l4d2-manager-web/`，核心文件包括：
- `app.py`：Web/API 服务，默认监听 `8080/tcp`。
- `l4d2-webctl`：受限 root helper，只暴露经过校验的管理子命令。
- `vpk_extract.py`：地图类 VPK 的受限提取工具，只提取允许的游戏资源目录。
- `l4d2-manager-web.service`：systemd unit，用于常驻运行 Web 服务。
- `l4d2-manager-web.sudoers`：sudoers 白名单，只允许 Web 用户调用指定 helper 和重启指定房间服务。
- `install.sh`：把上述文件安装到服务器对应位置的部署入口。

当前面板提供的功能边界：
- 查看 Room 1 / Room 2 状态、端口监听和默认地图。
- 重启指定房间。
- 按“战役 -> 子地图”二级选择默认地图，并可选择只保存或保存后重启房间。
- `Search & Install` 以 Steam Workshop 搜索为主，GameMaps 作为受控兜底来源；也保留手动输入 Workshop ID 的安装入口。
- Workshop 安装使用 `install-workshop <map|mod> <workshop_id>`；GameMaps 只允许 `install-gamemaps-map <numeric_id>`，不支持任意 URL 下载。
- 安装任务在后台执行，页面显示进度条、当前阶段和分包进度；job 状态持久化到 `/var/lib/l4d2-manager-web/jobs/`，刷新页面后仍可查看未完成或历史任务，并可提前取消仍在排队或运行中的任务。
- 区分 Map Packages 与 Mod Management，避免把含地图的 VPK 当作普通 Mod 管理；地图包支持 `Reinstall`、普通删除和彻底删除。
- Transfer 区域推荐使用轻量 JSON Manifest 迁移 Workshop 地图和 Mod 的 ID 与来源记录；导入后由用户手动重新下载。大文件 `.vpk` / 迁移 ZIP 仍保留为离线迁移方式。
- 启用/禁用已有 `.vpk`，仅在 `addons/` 与 `addons_disabled/` 之间移动文件，不提供删除和任意 shell 输入。
- 地图列表会识别 loose `.bsp`，也会索引启用 VPK 内的 `maps/*.bsp` 与 `missions/*.txt`，并按战役分组展示；mission parser 支持非固定顶层 key，可识别 Glubtastic 4/5 这类自定义 mission。
- Web 面板会维护地图包来源记录，例如 `/var/lib/l4d2-manager-web/packages.json`，用于展示来源链接、重装入口和普通删除后的恢复入口。
- GameMaps 可能被 Cloudflare 阻断，页面应显示失败 job；`Run To The Hills` 已验证可通过 Workshop `2232584588` 安装，章节地图为 `rh_map01` 到 `rh_map05`。

部署步骤：
```bash
# 本地仓库中执行，将部署包同步到服务器临时目录
ssh myubuntu "mkdir -p /tmp/l4d2-manager-web"
scp deploy/l4d2-manager-web/* myubuntu:/tmp/l4d2-manager-web/

# 服务器上安装/更新 Web 面板
ssh myubuntu "cd /tmp/l4d2-manager-web && sudo bash install.sh"
```

安装脚本会：
- 创建或复用系统用户 `l4d2web`。
- 安装 Web 程序到 `/opt/l4d2-manager-web/`。
- 安装 helper 到 `/usr/local/bin/l4d2-webctl`。
- 安装 systemd unit 到 `/etc/systemd/system/l4d2-manager-web.service`。
- 安装 sudoers 白名单到 `/etc/sudoers.d/l4d2-manager-web`。
- 首次部署时生成 `/etc/l4d2-manager-web.env`，后续部署保留已有登录配置。
- `daemon-reload` 后启用并重启 `l4d2-manager-web.service`。

安全注意事项：
- 面板浏览器入口使用页面内登录表单和 session cookie；脚本仍兼容 Basic Authorization。登录配置保存在服务器 `/etc/l4d2-manager-web.env`；文档、Issue、提交说明和聊天记录中不要记录真实密码。
- 访问面板需要同时放行服务器本机防火墙和云安全组的 `8080/tcp`。
- 所有需要 root 权限的操作必须经过 `/usr/local/bin/l4d2-webctl`，不要让 Web 服务执行任意 shell。
- sudoers 只白名单以下能力：重启 `l4d2` / `l4d2_2`、`set-default-map`、`install-workshop`、`install-gamemaps-map`、`set-addon-state`、`delete-map-package`、`cleanup-job-temp`、`import-vpk`、`import-export-zip`。
- 普通删除只删除本地地图包和已提取文件，但保留来源记录以便重装；彻底删除会同时移除来源记录，后续需要重新搜索或重新输入 Workshop ID。
- GameMaps 入口只接受数字 details id，并从 `https://www.gamemaps.com/details/<id>` 派生下载；不要增加任意 URL 输入框。
- 不要把 RCON 密码、GSLT、Steam token、SSH 私钥、代理订阅或 Web 登录密码写入公开文档。

常用检查命令：
```bash
sudo systemctl status l4d2-manager-web --no-pager
sudo systemctl restart l4d2-manager-web
sudo ss -H -ltnp 'sport = :8080'
sudo test -f /etc/l4d2-manager-web.env
```

部署后验证：
```bash
sudo python3 /tmp/l4d2-manager-web/verify_api.py
sudo python3 /tmp/l4d2-manager-web/verify_home.py
sudo python3 /tmp/l4d2-manager-web/verify_phase3.py
```

安装地图前后确认不会自动重启房间：
```bash
sudo systemctl show l4d2 l4d2_2 -p ExecMainStartTimestamp --no-pager
```

---

## 11. 常见问题 (FAQ)

### Q: 为什么服务器装了地图，我的本地电脑（客户端）还需要下载？
这是由 Source 引擎（L4D2 所使用的引擎）的架构决定的，并非 Bug：

1.  **资源分离**：服务器只负责计算游戏逻辑（僵尸在哪里、子弹打中没），而客户端负责渲染画面（模型、贴图、场景几何体）。这些巨大的资源文件（VPK/BSP）必须存在于你的本地硬盘上，电脑才能画出地图。
2.  **一致性检查**：为了防止作弊或模型错误，客户端和服务器的地图文件必须**完全一致**。
3.  **如何简化？**
    -   **手动安装**：将服务器上下载的 `.vpk` 文件也放到你本地电脑的 `left4dead2/addons` 文件夹下。
    -   **创意工坊**：最推荐的方法。如果你订阅了该地图，Steam 会自动帮你管理下载和更新。

### Q: 为什么我已经下载了地图，进入游戏时还会“重复下载”？
这种情况通常是由于 **“版本校验不一致”** 或 **“Steam 自动同步冲突”** 导致的：

1.  **版本微差**：如果服务器上的地图文件（手动解压的 BSP）与你本地创意工坊订阅的 VPK 版本有极细微的差别（哪怕只是日期戳不同），游戏引擎就会认为你没有这张图，强制通过服务器内置的慢速通道重新下载到你的 `left4dead2/downloads` 文件夹。
2.  **创意工坊同步问题**：Steam 有时会因为网络波动认为本地文件损坏，从而反复触发验证和下载。
3.  **解决方法**：
    -   **最彻底方案**：取消创意工坊订阅，手动将服务器使用的那个 `.vpk` 文件下载到你本地电脑的 `common/Left 4 Dead 2/left4dead2/addons` 目录下。
    -   **清理缓存**：删除本地电脑 `left4dead2/downloads` 文件夹下的所有内容，防止旧的残余文件干扰校验。
    -   **检查冲突**：确保 `addons` 文件夹里没有两个不同版本的同一张地图。

---

## 12. 本地地图备份与应急恢复

为了防止 Steam 创意工坊同步失败 or 文件意外丢失，我们在本地建立了备份目录。

### A. 备份目录位置
- **路径**：`D:\Steam\steamapps\common\Left 4 Dead 2\left4dead2\addons\workshop_backup`
- **用途**：存放从服务器下载的原始 `.vpk` 文件或已确认稳定的地图备份。

### B. 应急恢复流程
如果发现某张地图在进入游戏时反复下载，或提示“Map Missing”：
1.  进入上述 `workshop_backup` 目录。
2.  将对应的 `.vpk` 文件复制。
3.  粘贴到上一级目录 `addons` 中（直接放在 `addons` 根目录，不要放进 `workshop` 子目录）。
4.  重启游戏，游戏会优先加载 `addons` 目录下的手动安装文件。

### C. 如何手动建立备份 (本地终端)
如果您想将当前地图备份，可以在本地终端执行以下命令：

```powershell
# 1. 备份当前默认地图 MTL Gone To Hell
curl -o "D:\Steam\steamapps\common\Left 4 Dead 2\left4dead2\addons\workshop_backup\mtlgth.vpk" "https://cdn.steamusercontent.com/ugc/29934071615638932/7C5A842BFEF692694EB6EF1E0F6021585B9C6EEB/"

# 2. 备份 Yama 完整版 (假设 ID 为 2498978864)
copy "D:\Steam\steamapps\common\Left 4 Dead 2\left4dead2\addons\workshop\2498978864.vpk" "D:\Steam\steamapps\common\Left 4 Dead 2\left4dead2\addons\workshop_backup\yama_full.vpk"

# 3. 备份 HOME TOWN 1.0 Modified
curl -o "D:\Steam\steamapps\common\Left 4 Dead 2\left4dead2\addons\workshop_backup\hometown.vpk" "https://cdn.steamusercontent.com/ugc/2494507236830147734/758B7F4410E5E3685C946A498F338AE47A66F11C/"
```

---

## 13. 插件与 Mod 管理 (Addons Management)

除了地图，服务器还可以通过 VPK 插件增强功能（如提升 Bot 智商、增加管理员菜单）。

### A. 常用插件推荐
- **Left 4 Bots 2** (ID: `2279814689`): 极大提升 Bot 智商，支持指令指挥。*（依赖 Left 4 Lib）*
- **Left 4 Lib** (ID: `2634208272`): 核心前置库。
- **Admin System** (ID: `213591107`): 提供游戏内管理员指令（如 `!give`, `!kick`）。

### B. 快速安装 Mod (API 直链方式)
**不要使用官方 `steamcmd` 下载 Mod**，因为其在国内极易失败。建议使用以下流程：

1.  **获取直链**：
    ```bash
    ssh myubuntu "curl -s -d 'itemcount=1&publishedfileids[0]=<Mod_ID>' -X POST https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
    ```
2.  **下载并部署**：
    ```bash
    # 在服务器执行
    curl -L -o /tmp/mod.vpk "<file_url>"
    sudo cp /tmp/mod.vpk /opt/l4d2/left4dead2/addons/
    sudo chown steam:steam /opt/l4d2/left4dead2/addons/mod.vpk
    sudo systemctl restart l4d2        # Room 1
    sudo systemctl restart l4d2_2      # Room 2 如需同步生效
    ```

### C. 设置管理员权限 (EMS 插件)
对于 **Left 4 Bots** 或 **Admin System**，需要将你的 SteamID 加入白名单：
- **文件路径**：
  - L4B2: `/opt/l4d2/left4dead2/ems/left4bots/cfg/admins.txt`
  - Admin System: `/opt/l4d2/left4dead2/ems/admin system/admins.txt`
- **格式**：`STEAM_1:0:XXXXXXXX //你的昵称`

---

## 14. 多实例（多房间）配置指南

为了让更多朋友同时玩，可以在同一台服务器上运行多个 L4D2 实例。

### A. 核心配置逻辑
- **端口隔离**：每个房间必须使用唯一的端口（例如 27015, 27016）。
- **防火墙放行**：除了在云服务商控制台开启端口外，还必须在服务器系统内部放行 UDP 端口。
  ```bash
  sudo ufw allow 27016/udp
  ```
- **脚本隔离**：每个房间拥有独立的启动脚本（指定不同的端口 and 默认地图）。
- **服务隔离**：每个房间配置独立的 Systemd 服务。

### B. 当前房间配置详情

Room 1：
- **服务**：`l4d2.service`
- **端口**：`27015`
- **配置文件**：`server.cfg`
- **默认地图**：`hls_05`
- **启动脚本**：`/opt/l4d2/start_l4d2.sh`

Room 2：
- **服务**：`l4d2_2.service`
- **端口**：`27016`
- **配置文件**：`server_2.cfg`
- **默认地图**：`zc_m1`
- **启动脚本**：`/opt/l4d2/start_l4d2_2.sh`

### C. 管理指令
- **启动/重启房间 2**：
  ```bash
  ssh myubuntu "sudo systemctl restart l4d2_2"
  ```
- **查看房间 2 状态**：
  ```bash
  ssh myubuntu "sudo systemctl status l4d2_2"
  ```
- **查看房间 2 日志**：
  ```bash
  ssh myubuntu "sudo journalctl -u l4d2_2.service -f"
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
sv_steamgroup_exclusive 1      // 仅限 Steam 成员
sv_allow_lobby_connect_only 1  // 必须通过大厅组队才能进入
```

**修改后必须重启对应房间的服务生效。**

---

## 15. 常用管理指令汇总

- **查看服务状态**：`ssh myubuntu "sudo systemctl status l4d2"` (Room 1) 或 `l4d2_2` (Room 2)
- **重启服务**：`ssh myubuntu "sudo systemctl restart l4d2"`
- **查看实时日志**：`ssh myubuntu "sudo journalctl -u l4d2.service -f"`
- **查看端口监听**：`ssh myubuntu "sudo ss -H -lunp 'sport = :27015'"` 或 `27016`
- **查看最近错误**：`ssh myubuntu "sudo journalctl -u l4d2 -u l4d2_2 --since '24 hours ago' --no-pager | grep -Ei 'error|fail|warning|missing|keyvalues' | tail -80"`

---

## 16. 申请与配置 GSLT 提升权重

**GSLT (Game Server Login Token)** 是让服务器获得“官方身份认证”的关键，能显著提升全球搜索排名。

### A. 申请步骤
1. 访问 [Steam 游戏服务器账户管理](https://steamcommunity.com/dev/managegameservers)。
2. AppID 填写 `550`。
3. 生成并复制令牌。

### B. 配置方法
在启动脚本（如 `start_l4d2.sh`）的启动命令末尾增加：
`+sv_setsteamaccount YOUR_GSLT_TOKEN`

---
*Generated on: 2026-05-01*
