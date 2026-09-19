---
name: "l4d2-troubleshooting"
description: "L4D2 服务器排障与常见问题。当需要做标准健康检查（systemd 状态/端口监听/日志过滤）、定位日志噪声与自定义资源报错、修复 KeyValues Error（RecursiveLoadFromBuffer）、处理文件权限问题、修复 IPv6 导致的 Steam/下载超时（gai.conf 强制 IPv4），或解答客户端为何重复下载地图等 FAQ 时调用。不负责服务器搭建、地图安装或插件安装的常规流程。"
---

# L4D2 服务器排障与常见问题

本 skill 覆盖服务器运行期的健康检查、日志排错与玩家侧常见疑问。常规的服务器搭建见 `l4d2-server-setup`；地图安装/切换见 `l4d2-map-manager`；插件相关报错见 `l4d2-plugin-manager`。

> 安全规范：展示 `systemctl status`、`journalctl`、`server*.cfg` 等输出前，先把 `rcon_password`、GSLT、Steam token 替换为 `YOUR_RCON_PASSWORD` 等占位符。改变服务器状态前优先做只读健康检查。

---

## 1. 常见问题排查 (Troubleshooting)

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

### E. IPv6 导致 Steam / 下载连接超时（强制 IPv4）

当服务器有 IPv6 地址但 IPv6 出网不可达时，`getaddrinfo` 默认优先返回 IPv6，导致 `steamcmd`、Steam API、GitHub 下载等长时间卡住或超时。修复方式是在 `/etc/gai.conf` 中提升 IPv4 映射地址的优先级：

```bash
# 备份后追加（只需一次）
sudo cp /etc/gai.conf /etc/gai.conf.orig-backup 2>/dev/null
echo 'precedence ::ffff:0:0/96 100' | sudo tee -a /etc/gai.conf
```

加上该行后，系统会优先使用 IPv4 解析结果，无需逐个命令加 `-4`。Web 面板的下载 helper 另外内置了 `open_with_retries()` / `_download_once()` 的多次重试与断点续传，遇到瞬时网络抖动会自动重试，不要因为单次失败就反复手动重跑。

---

## 2. 常见问题 (FAQ)

### Q: 为什么服务器装了地图，我的本地电脑（客户端）还需要下载？
这是由 Source 引擎（L4D2 所使用的引擎）的架构决定的，并非 Bug：

1.  **资源分离**：服务器只负责计算游戏逻辑（僵尸在哪里、子弹打中没），而客户端负责渲染画面（模型、贴图、场景几何体）。这些巨大的资源文件（VPK/BSP）必须存在于你的本地硬盘上，电脑才能画出地图。
2.  **一致性检查**：为了防止作弊或模型错误，客户端和服务器的地图文件必须**完全一致**。
3.  **如何简化？**
    -   **手动安装**：将服务器上下载的 `.vpk` 文件也放到你本地电脑的 `left4dead2/addons` 文件夹下。
    -   **创意工坊**：最推荐的方法。如果你订阅了该地图，Steam 会自动帮你管理下载和更新。

### Q: 为什么我已经下载了地图，进入游戏时还会"重复下载"？
这种情况通常是由于 **"版本校验不一致"** 或 **"Steam 自动同步冲突"** 导致的：

1.  **版本微差**：如果服务器上的地图文件（手动解压的 BSP）与你本地创意工坊订阅的 VPK 版本有极细微的差别（哪怕只是日期戳不同），游戏引擎就会认为你没有这张图，强制通过服务器内置的慢速通道重新下载到你的 `left4dead2/downloads` 文件夹。
2.  **创意工坊同步问题**：Steam 有时会因为网络波动认为本地文件损坏，从而反复触发验证和下载。
3.  **解决方法**：
    -   **最彻底方案**：取消创意工坊订阅，手动将服务器使用的那个 `.vpk` 文件下载到你本地电脑的 `common/Left 4 Dead 2/left4dead2/addons` 目录下。
    -   **清理缓存**：删除本地电脑 `left4dead2/downloads` 文件夹下的所有内容，防止旧的残余文件干扰校验。
    -   **检查冲突**：确保 `addons` 文件夹里没有两个不同版本的同一张地图。

> 与"重复下载"相关的本地地图备份与应急恢复流程，见 `l4d2-map-manager`。
