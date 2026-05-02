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

## 0. 服务器基础环境配置

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

## 1. L4D2 服务安装与运行

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

## 2. 安装新的创意工坊地图

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

## 3. 手动提取 VPK 资源 (推荐)

为了服务器稳定性，建议将 VPK 内容直接提取到游戏核心目录。

**步骤：**
1. 使用本地的 `vpk_extract.py` 脚本提取 VPK：
   ```bash
   python3 vpk_extract.py <VPK路径> <目标提取目录>
   ```
2. 将提取出的文件夹（如 `maps`, `missions`, `materials`, `models`, `sound`）同步到服务器的 `/opt/l4d2/left4dead2/` 目录下。

---

## 4. 修改服务器默认启动地图

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

## 5. 游戏内实时切换地图 (RCON)

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

## 6. 已安装地图的快速切换

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

## 7. 常见问题排查 (Troubleshooting)

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

## 8. 存储管理与旧地图清理

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

## 9. 服务器远程管理技巧 (SSH)

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

## 10. 常见问题 (FAQ)

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

## 11. 本地地图备份与应急恢复

为了防止 Steam 创意工坊同步失败或文件意外丢失，我们在本地建立了备份目录。

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

## 12. 插件与 Mod 管理 (Addons Management)

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

## 13. 多实例（多房间）配置指南

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
sv_steamgroup_exclusive 1      // 仅限 Steam 组成员
sv_allow_lobby_connect_only 1  // 必须通过大厅组队才能进入
```

**修改后必须重启对应房间的服务生效。**

---

## 14. 常用管理指令汇总

- **查看服务状态**：`ssh myubuntu "sudo systemctl status l4d2"` (Room 1) 或 `l4d2_2` (Room 2)
- **重启服务**：`ssh myubuntu "sudo systemctl restart l4d2"`
- **查看实时日志**：`ssh myubuntu "sudo journalctl -u l4d2.service -f"`
- **查看端口监听**：`ssh myubuntu "sudo ss -H -lunp 'sport = :27015'"` 或 `27016`
- **查看最近错误**：`ssh myubuntu "sudo journalctl -u l4d2 -u l4d2_2 --since '24 hours ago' --no-pager | grep -Ei 'error|fail|warning|missing|keyvalues' | tail -80"`

---

## 15. 申请与配置 GSLT 提升权重

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
