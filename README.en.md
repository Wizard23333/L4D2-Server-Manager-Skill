# L4D2 Server Setup and Map Management Guide

English | [Simplified Chinese](./README.md)

This guide documents the setup and day-to-day management workflow for a Left 4 Dead 2 dedicated server, including environment preparation, Steam connectivity workarounds, service management, custom map deployment, and RCON-based map switching.

---

## Project Scope

This repository provides a server management skill / playbook and an operational reference for L4D2 server owners. It turns server health checks, map installation, RCON map switching, multi-room management, log triage, and secret redaction into a reusable workflow.

The repository includes [skills/l4d2-manager/SKILL.md](./skills/l4d2-manager/SKILL.md), which can be installed directly in Codex, but the workflow itself is not Codex-specific. You can also use it as project context for Cursor, Trae, Windsurf, Claude Code, GitHub Copilot Chat, or another AI IDE/agent. It is equally useful as a human-readable runbook for manual SSH operations.

Good fit for:

- Server owners who already run a Linux-based L4D2 dedicated server and want AI IDE, agent, or manual SSH-assisted operations.
- Setups that manage Workshop maps, VPK files, addons, RCON, and Systemd services.
- Maintainers who want a documented, auditable workflow instead of one-off shell commands.

Not intended for:

- Replacing server hardening, cloud firewall rules, or general Linux security work.
- Storing real RCON passwords, GSLT values, SSH private keys, proxy subscriptions, or Steam credentials.
- Blindly running destructive commands without reviewing the target service, path, and expected impact.

---

## Quick Start

### Use as a Codex Skill

Copy the skill directory into the Codex user skills directory:

```powershell
Copy-Item -Recurse .\skills\l4d2-manager "$env:USERPROFILE\.codex\skills\l4d2-manager"
```

Restart Codex after installation so the skill can be loaded. You can then invoke it with `$l4d2-manager`, or simply describe an L4D2 server management task in the conversation.

### Use With Other AI IDEs or Agents

If your tool supports project rules, context files, or custom instructions, include these files as context:

- `skills/l4d2-manager/SKILL.md`
- `L4D2_MAP_SKILL.md`
- `README.md`

A good task framing is: "Follow this repository's L4D2 server management playbook." Ask the tool to confirm the target room, target map, restart impact, and any sensitive output before executing remote commands.

### Compatibility Path

The repository still keeps `.trae/skills/l4d2-manager/SKILL.md` for Trae and existing workflows. For public distribution and new installs, prefer `skills/l4d2-manager/SKILL.md`.

### Recommended Setup

- Configure an SSH alias such as `myubuntu` in local `~/.ssh/config`.
- Run the L4D2 dedicated server under a non-root user such as `steam`.
- Keep real secrets only in server configuration files or private local environments.
- Read the health-check and secret-redaction sections in [L4D2_MAP_SKILL.md](./L4D2_MAP_SKILL.md) before using the workflow on a public server.

### Example Prompts

```text
$l4d2-manager check the current status of both rooms
$l4d2-manager inspect the last 24 hours of L4D2 errors and tell me whether players are affected
$l4d2-manager help me install Workshop map 3526529688 on the server
$l4d2-manager switch Room 2 to zc_m1 and tell me whether a restart is required
$l4d2-manager inspect addons, maps, and workshop cache usage, then suggest cleanup steps
```

---

## Key Features

- **Steam connectivity workarounds**: Hosts and proxy patterns for servers whose routes to Steam or the Workshop are slow or unreliable.
- **Automated management**: Clash plus Proxychains workflow for making `steamcmd` and related downloads more stable.
- **Manual VPK extraction**: Recommended workflow for extracting VPK content into the game directory when direct addon loading is not enough.
- **Fast map switching**: RCON commands for changing maps without restarting the server.
- **Remote operations**: SSH alias usage for repeatable server maintenance.
- **Troubleshooting notes**: Practical fixes for common issues such as KeyValues errors, missing resources, and repeated client downloads.
- **Secret redaction**: Public docs use placeholders only and do not record real RCON passwords, GSLT values, Steam tokens, or SSH credentials.

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
