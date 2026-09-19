# Agent Instructions

This repository packages a set of focused L4D2 agent skills and supporting documentation for managing Left 4 Dead 2 dedicated servers. The skills follow Progressive Disclosure: `l4d2-manager` is the index/router, and detailed operations live in six focused sub-skills.

When the user asks about L4D2 server operations, first consult the index `skills/l4d2-manager/SKILL.md` for the server snapshot, safety rules, and routing, then read and follow the relevant focused skill:

- `skills/l4d2-manager/SKILL.md` — index/router: server snapshot, safety rules, sub-skill navigation, quick command reference.
- `skills/l4d2-server-setup/SKILL.md` — first-time server onboarding, SSH hardening & firewall, Steam CDN/proxy, systemd service install/run, multi-room (multi-instance) config, room visibility, GSLT.
- `skills/l4d2-map-manager/SKILL.md` — Workshop map install, VPK extraction, default map change, RCON live map switching, fast switching of installed maps, storage cleanup, local map backup/recovery.
- `skills/l4d2-plugin-manager/SKILL.md` — VPK mod management, in-game admin permissions, MetaMod+SourceMod plugin stack, self-authored SourcePawn + spcomp64 compilation, panel dynamic-scan enable/disable, rollback.
- `skills/l4d2-troubleshooting/SKILL.md` — standard health checks, log noise triage, KeyValues errors, permissions, IPv6/gai.conf force IPv4, client re-download FAQ.
- `skills/l4d2-web-panel/SKILL.md` — optional Web management panel deployment, capability boundaries, sudoers/helper security, verification.
- `skills/l4d2-backup-migrate/SKILL.md` — full server state backup and cross-machine migration on lease expiry/relocation: complete migration of configs, systemd units, SourceMod plugin stack (incl. disabled state), self-authored .sp sources, admin allowlists, /etc/hosts CDN and /etc/gai.conf network acceleration, and Web panel env/packages.json; maps keep only Workshop IDs for re-download on the new host.

Operational safety:

- Do not expose real RCON passwords, GSLT values, Steam tokens, SSH private keys, proxy subscriptions, or server credentials.
- Replace secrets in command output with placeholders such as `YOUR_RCON_PASSWORD` and `YOUR_GSLT_TOKEN`.
- Confirm the target room, target map, restart impact, and destructive file operations before acting.
- Prefer read-only health checks before changing server state.
