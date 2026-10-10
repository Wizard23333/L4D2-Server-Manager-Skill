---
name: "l4d2-map-manager"
description: "L4D2 服务器地图管理。当需要安装创意工坊地图（Steam API/aria2c/l4d2-add-map）、手动提取 VPK 资源、修改服务器默认启动地图、通过 RCON 实时切换地图、查看与快速切换已安装地图、清理旧地图释放磁盘空间，或做本地地图备份与应急恢复时调用。不负责服务器搭建、SourceMod 插件或 Web 面板。"
---

# L4D2 地图管理

本 skill 覆盖地图的「安装 -> 提取 -> 默认地图 -> RCON 切图 -> 快速切换 -> 清理 -> 本地备份恢复」。服务器搭建/systemd 见 `l4d2-server-setup`；VPK 插件 Mod 见 `l4d2-plugin-manager`；报错排查见 `l4d2-troubleshooting`。

> 安全规范：展示 `start_l4d2*.sh`、`server*.cfg` 或 RCON 相关输出前，把 `rcon_password`、GSLT、Steam token 替换为 `YOUR_RCON_PASSWORD` 等占位符。切图/重启前确认目标房间与在线影响。

## 当前已安装的自定义战役（2026-10-10 核验）

当前机器 `addons/` 下 12 个 VPK、`maps/` 下 65 个 `.bsp`，自定义战役共 3 套：

- **Back To School（返校）** 6 章：`l4d2_bts01_forest`、`l4d2_bts02_station`、`l4d2_bts03_town`、`l4d2_bts04_cinema`、`l4d2_bts05_church`、`l4d2_bts06_school`。**Room 1 默认图即 `l4d2_bts01_forest`。**
- **Glubtastic 5** 6 章 +  extras：`glubtastic5_1` ~ `glubtastic5_6`、`glubtastic5_bigtesco`。**Room 2 默认图即 `glubtastic5_1`。**
- **Ladder to Heaven 3（天梯 3）**：`hls_15` ~ `hls_20`。

另有 3 个装饰 mod VPK（Military Tank / Policeman Tank / Soviet Teddy Bear Gnome），以及 L4D1 原版战役（`c1m1_hotel` ~ `c5m5_bridge`）与 No Special 自带图。

> ⚠️ 旧机上的广州增城 `zc_m*`、地心引力 `dxyl*`、`l4d_yama*`、`mtlgth*`、`q_ancienttown*`（HOME TOWN）以及 `gzzc7.3.vpk` / `tianti.vpk` 在当前机器上**均未安装**。需要时按 Workshop ID 重新安装（见第 1 节），不要直接 `changelevel` 到不存在的地图。

占用参考：`addons/` 2.4G、`maps/` 2.0G、`missions/` 40K。

---

## 1. 安装新的创意工坊地图

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
ssh myubuntu2 "sudo systemctl restart l4d2"
ssh myubuntu2 "sudo systemctl restart l4d2_2"
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

> 通过 Web 面板搜索安装（Steam Workshop / GameMaps）见 `l4d2-web-panel`。

---

## 2. 手动提取 VPK 资源 (推荐)

为了服务器稳定性，建议将 VPK 内容直接提取到游戏核心目录。

**步骤：**
1. 使用本地的 `vpk_extract.py` 脚本提取 VPK：
   ```bash
   python3 vpk_extract.py <VPK路径> <目标提取目录>
   ```
2. 将提取出的文件夹（如 `maps`, `missions`, `materials`, `models`, `sound`）同步到服务器的 `/opt/l4d2/left4dead2/` 目录下。

---

## 3. 修改服务器默认启动地图

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

## 4. 游戏内实时切换地图 (RCON)

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

## 5. 已安装地图的快速切换

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

## 6. 存储管理与旧地图清理

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
ssh myubuntu2 "df -h /opt/l4d2"
ssh myubuntu2 "sudo du -sh /opt/l4d2/left4dead2/addons /opt/l4d2/left4dead2/maps /opt/l4d2/left4dead2/missions /opt/l4d2/left4dead2/downloads 2>/dev/null"
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

## 7. 本地地图备份与应急恢复

为了防止 Steam 创意工坊同步失败或文件意外丢失，在本地建立了备份目录。

### A. 备份目录位置
- **路径**：`D:\Steam\steamapps\common\Left 4 Dead 2\left4dead2\addons\workshop_backup`
- **用途**：存放从服务器下载的原始 `.vpk` 文件或已确认稳定的地图备份。

### B. 应急恢复流程
如果发现某张地图在进入游戏时反复下载，或提示“Map Missing”：
1.  进入上述 `workshop_backup` 目录。
2.  将对应的 `.vpk` 文件复制。
3.  粘贴到上一级目录 `addons` 中（直接放在 `addons` 根目录，不要放进 `workshop` 子目录）。
4.  重启游戏，游戏会优先加载 `addons` 目录下的手动安装文件。

> 客户端为何会“重复下载”的原理与彻底解决方案，见 `l4d2-troubleshooting` 的 FAQ。

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
