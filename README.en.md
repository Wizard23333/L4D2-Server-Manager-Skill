# L4D2 Server Setup and Map Management Guide

English | [Simplified Chinese](./README.md)

This guide documents the setup and day-to-day management workflow for a Left 4 Dead 2 dedicated server, including environment preparation, Steam connectivity workarounds, service management, custom map deployment, and RCON-based map switching.

---

## Key Features

- **Steam connectivity workarounds**: Hosts and proxy patterns for servers whose routes to Steam or the Workshop are slow or unreliable.
- **Automated management**: Clash plus Proxychains workflow for making `steamcmd` and related downloads more stable.
- **Manual VPK extraction**: Recommended workflow for extracting VPK content into the game directory when direct addon loading is not enough.
- **Fast map switching**: RCON commands for changing maps without restarting the server.
- **Remote operations**: SSH alias usage for repeatable server maintenance.
- **Troubleshooting notes**: Practical fixes for common issues such as KeyValues errors, missing resources, and repeated client downloads.

---

## 1. Base Server Environment

Before installing the game server, prepare the network path to Steam. This is especially useful on cloud hosts or networks where Steam CDN and Workshop access may be slow, blocked, or unstable.

- **Steam CDN tuning**: Adjust `/etc/hosts` when a known fast CDN endpoint is needed.
- **Proxy configuration**: Use Clash plus Proxychains4 to route `steamcmd` traffic through a stable proxy.

## 2. L4D2 Service Installation and Runtime

- **Install path**: `/opt/l4d2`, running under the non-root `steam` user.
- **Startup scripts**: Define core launch parameters such as `+sv_hibernate_when_empty 0` so RCON remains available.
- **Systemd services**: Use Systemd for auto-start and crash recovery. This setup currently maintains two rooms: `l4d2` and `l4d2_2`.

## Current Server Layout

- **Room 1**: `l4d2.service`, `27015/udp`, default map `hls_05`, intended for Steam group or private access.
- **Room 2**: `l4d2_2.service`, `27016/udp`, default map `zc_m1`, public and searchable.
- **Health checks**: Service status, UDP listeners, and recent error-log filters are documented in the detailed skill guide.

## 3. Map Installation and Management

- **Automated install**: Use the `l4d2-add-map` script or the Steam Web API download flow.
- **Manual extraction**: Use `vpk_extract.py` to extract VPK contents into the game directory. This is recommended for stability when maps include missions, models, materials, and other loose assets.
- **Default map**: Change the `+map` parameter in `start_l4d2.sh` or `start_l4d2_2.sh`.

## 4. Live Map Switching With RCON

You can change maps without restarting the server from the in-game console:

1. `rcon_password "YOUR_RCON_PASSWORD"`
2. `rcon changelevel <map_name>`
3. To inspect available maps on the server: `ls /opt/l4d2/left4dead2/maps/*.bsp`

## 5. Storage Management and Cleanup

Clean these locations regularly to avoid filling the server disk:

- Old VPK files in `/opt/l4d2/left4dead2/addons/`.
- Workshop or download cache files under `/home/steam/Steam/steamapps/workshop/content/550/`.

## 6. Troubleshooting and SSH Tips

- **KeyValues Error**: Check for UTF-8 BOM markers, malformed braces, or incompatible custom resources.
- **SSH alias**: Configure an alias in local `~/.ssh/config` so repeated operations can use short commands such as `ssh myubuntu "sudo systemctl status l4d2"`.

## 7. Local Backups and Recovery

- **Backup directory**: Keep known-good VPK files in a local `addons/workshop_backup` directory.
- **Emergency recovery**: If a map repeatedly downloads or appears missing, copy the verified VPK into the root `addons` directory instead of the `workshop` subdirectory.

## 8. FAQ

- **Why do clients still need to download a map after the server installs it?**  
  The Source engine separates server-side game logic from client-side rendering assets. Clients still need the matching map files locally.

- **Why does the game repeatedly download a map I already have?**  
  This usually means the server and client map files do not match exactly, or Steam Workshop sync has left stale files behind. Use one verified VPK version on both sides and clear `left4dead2/downloads` if needed.

---

## Detailed Documentation

See [L4D2_MAP_SKILL.md](./L4D2_MAP_SKILL.md) for the full operational guide, command references, multi-room configuration, installed map list, and current server health-check workflow.

---

## More Resources

- [GitHub Profile](https://github.com/Wizard23333)
- [Personal Blog](https://wizard23333.github.io/)

---

*Generated on: 2026-05-03*
