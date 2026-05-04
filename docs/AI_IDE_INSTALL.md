# AI IDE Installation Guide

This repository keeps one canonical skill:

```text
skills/l4d2-manager/SKILL.md
```

Use this file directly in AI tools that support `SKILL.md`. For tools that do not load skills natively, add a small rule or custom-instructions file that tells the agent to read `skills/l4d2-manager/SKILL.md` before doing L4D2 server work.

Do not copy real RCON passwords, GSLT values, Steam tokens, SSH private keys, proxy subscriptions, or server credentials into any shared skill, rule, prompt, issue, or README.

---

## Quick Compatibility Matrix

| Tool | Best integration | Project path | Global path | Invocation |
| --- | --- | --- | --- | --- |
| Codex / OpenAI Skills | Native `SKILL.md` skill | `skills/l4d2-manager/` in this repo, or install into Codex | `$CODEX_HOME/skills/l4d2-manager`, usually `~/.codex/skills/l4d2-manager` | `$l4d2-manager` or natural language |
| Claude Code | Native Agent Skill | `.claude/skills/l4d2-manager/` | `~/.claude/skills/l4d2-manager/` | Auto, or `/l4d2-manager` where supported |
| Windsurf Cascade | Native Cascade Skill | `.windsurf/skills/l4d2-manager/` | `~/.codeium/windsurf/skills/l4d2-manager/` | Auto, or `@l4d2-manager` |
| Cline | Native Skill, experimental | `.cline/skills/l4d2-manager/` | `~/.cline/skills/l4d2-manager/` | Auto after Skills are enabled |
| Cursor | Project Rule or `AGENTS.md` | `.cursor/rules/l4d2-manager.mdc` or root `AGENTS.md` | User Rules in Cursor settings | Agent decides, or `@ruleName` |
| GitHub Copilot | Repository custom instructions | `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`, or root `AGENTS.md` | Personal / organization instructions | Automatic when custom instructions are enabled |
| Continue | Local Rule | `.continue/rules/l4d2-manager.md` | Hub Rules | Automatic in Agent, Chat, and Edit modes |
| Generic agents | `AGENTS.md` | root `AGENTS.md` | Tool-specific user instructions | Automatic if the tool supports `AGENTS.md` |

---

## Codex / OpenAI Skills

Codex and OpenAI Skills use the Agent Skills structure: a directory containing `SKILL.md` plus optional resources.

Install locally from a cloned repository.

PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills" | Out-Null
Copy-Item -Recurse -Force .\skills\l4d2-manager "$env:USERPROFILE\.codex\skills\l4d2-manager"
```

macOS / Linux:

```bash
mkdir -p ~/.codex/skills
cp -R skills/l4d2-manager ~/.codex/skills/l4d2-manager
```

Restart Codex after installation. Then ask:

```text
$l4d2-manager check both L4D2 rooms
```

If the skill is hosted on GitHub, Codex users can also ask the built-in skill installer to install the GitHub directory URL:

```text
$skill-installer install https://github.com/Wizard23333/L4D2-Server-Manager-Skill/tree/main/skills/l4d2-manager
```

---

## Claude Code

Claude Code supports filesystem-based Agent Skills.

Project skill:

```bash
mkdir -p .claude/skills
cp -R skills/l4d2-manager .claude/skills/l4d2-manager
```

Personal skill:

```bash
mkdir -p ~/.claude/skills
cp -R skills/l4d2-manager ~/.claude/skills/l4d2-manager
```

Claude Code discovers skills by their `name` and `description` fields. Keep the folder name and frontmatter name as `l4d2-manager`.

Optional fallback for older or constrained environments: create `CLAUDE.md` in the project root and point Claude to the canonical skill:

```markdown
# Project Instructions

For L4D2 server management tasks, read and follow @skills/l4d2-manager/SKILL.md before acting.
Never expose real RCON passwords, GSLT values, Steam tokens, SSH keys, or proxy credentials.
```

---

## Windsurf Cascade

Windsurf supports Cascade Skills with the same `SKILL.md` pattern.

Workspace skill:

```bash
mkdir -p .windsurf/skills
cp -R skills/l4d2-manager .windsurf/skills/l4d2-manager
```

Global skill:

```bash
mkdir -p ~/.codeium/windsurf/skills
cp -R skills/l4d2-manager ~/.codeium/windsurf/skills/l4d2-manager
```

Invoke it by describing an L4D2 server task, or mention it explicitly:

```text
@l4d2-manager inspect recent L4D2 server errors
```

Windsurf also understands `AGENTS.md`; this repository includes one as a lightweight cross-tool entry point.

---

## Cline

Cline supports Skills as an experimental feature. Enable it in Cline settings first:

```text
Settings -> Features -> Enable Skills
```

Project skill:

```bash
mkdir -p .cline/skills
cp -R skills/l4d2-manager .cline/skills/l4d2-manager
```

Global skill:

```bash
mkdir -p ~/.cline/skills
cp -R skills/l4d2-manager ~/.cline/skills/l4d2-manager
```

For rule-only setups, create `.clinerules/l4d2-manager.md`:

```markdown
# L4D2 Manager

For L4D2 server operations, read `skills/l4d2-manager/SKILL.md` first.
Confirm target room, target map, restart impact, and destructive operations before acting.
Never expose real RCON passwords, GSLT values, Steam tokens, SSH keys, or proxy credentials.
```

---

## Cursor

Cursor project rules live in `.cursor/rules` and use `.mdc` files.

Create `.cursor/rules/l4d2-manager.mdc`:

```mdc
---
description: Use this rule for Left 4 Dead 2 dedicated server management, map installation, RCON map switching, Systemd room checks, VPK extraction, addon cleanup, and server log triage.
globs:
alwaysApply: false
---

Read and follow @skills/l4d2-manager/SKILL.md before acting on L4D2 server management tasks.

Safety requirements:
- Confirm the target room, target map, restart impact, and destructive file operations before acting.
- Prefer read-only health checks before changing server state.
- Do not expose real RCON passwords, GSLT values, Steam tokens, SSH private keys, proxy subscriptions, or server credentials.
```

Users can also rely on the root `AGENTS.md` file included in this repository if their Cursor version has `AGENTS.md` support enabled.

---

## GitHub Copilot

For repository-wide Copilot Chat instructions, create `.github/copilot-instructions.md`:

```markdown
# Repository Instructions

This repository contains an L4D2 server management skill.

For L4D2 server operations, map installation, RCON map switching, Systemd room checks, VPK extraction, addon cleanup, or server log triage, read `skills/l4d2-manager/SKILL.md` before acting.

Never expose real RCON passwords, GSLT values, Steam tokens, SSH private keys, proxy subscriptions, or server credentials.
```

For Copilot agent workflows, the root `AGENTS.md` file in this repository provides a cross-tool entry point.

---

## Continue

Continue local rules live in `.continue/rules`.

Create `.continue/rules/l4d2-manager.md`:

```markdown
# L4D2 Manager

When the user asks about L4D2 server management, map installation, RCON, Systemd rooms, VPK extraction, addon cleanup, or log triage, read `skills/l4d2-manager/SKILL.md` first.

Confirm target room, target map, restart impact, and destructive operations before acting. Redact real secrets from all outputs.
```

---

## Minimal Prompt for Any AI IDE

If the tool has no built-in skill, rule, or instruction system, paste this at the start of the conversation:

```text
Use the repository playbook at skills/l4d2-manager/SKILL.md for all L4D2 server management tasks. Before running remote commands, confirm the target room, target map, restart impact, and whether any destructive operation is involved. Redact all real RCON passwords, GSLT values, Steam tokens, SSH private keys, proxy subscriptions, and server credentials from outputs.
```

---

## References

- OpenAI Skills / Codex skill catalog: https://github.com/openai/skills
- OpenAI Help Center, Skills in ChatGPT: https://help.openai.com/articles/20001066-skills-in-chatgpt
- Claude Code Agent Skills: https://docs.claude.com/en/docs/claude-code/skills
- Windsurf Cascade Skills: https://docs.windsurf.com/windsurf/cascade/skills
- Windsurf Memories & Rules: https://docs.windsurf.com/windsurf/cascade/memories
- Cline Skills: https://docs.cline.bot/customization/skills
- Cline Rules: https://docs.cline.bot/customization/cline-rules
- Cursor Rules: https://docs.cursor.com/en/context
- GitHub Copilot custom instructions: https://docs.github.com/en/copilot/how-tos/custom-instructions
- Continue Rules: https://docs.continue.dev/customize/rules
