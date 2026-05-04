# Agent Instructions

This repository packages the `l4d2-manager` agent skill and supporting documentation for managing Left 4 Dead 2 dedicated servers.

When the user asks about L4D2 server operations, map installation, RCON map switching, Systemd room management, VPK extraction, addon cleanup, or server log triage, read and follow:

- `skills/l4d2-manager/SKILL.md`

Operational safety:

- Do not expose real RCON passwords, GSLT values, Steam tokens, SSH private keys, proxy subscriptions, or server credentials.
- Replace secrets in command output with placeholders such as `YOUR_RCON_PASSWORD` and `YOUR_GSLT_TOKEN`.
- Confirm the target room, target map, restart impact, and destructive file operations before acting.
- Prefer read-only health checks before changing server state.
