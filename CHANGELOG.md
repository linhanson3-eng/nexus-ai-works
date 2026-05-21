# Changelog

## v1.0.0 (2026-05-21)

First stable release. All 8 phases complete.

### Core
- OrgEngine + Workshop system with runtime CRUD
- 4 Agent templates (super, reviewer, analyst, writer)
- FactoryAgentRunner with nanobot integration

### Memory
- 3-level Memory Tree (Source → Topic → Global)
- SQLite WAL + FTS5 full-text search
- Obsidian-compatible Markdown dual-write
- Bucket-Seal cascade compression
- TokenJuice: 5-step tool output compression (96 rules)

### Workflow
- DAG-based workflow execution engine
- 5 built-in templates (code-review, market-analysis, content-creation, legal-review, simple)
- Review gate with retry loop (pass/fail keywords)

### Kanban
- SQLite-backed Board/List/Card management
- Agent task auto-sync to kanban cards
- WebSocket real-time board updates

### MCP
- MCP client with stdio + streamable HTTP transport
- 6 built-in marketplace servers
- Tool discovery + invocation + local cache

### Skills
- Progressive disclosure Skill.md loader
- Workshop-level installation management
- YAML front matter parsing

### Channel
- Plugin-based channel adapter interface
- Global registry with inbound/outbound routing
- DummyChannel for development

### Evolution
- GEPA self-evolution engine (Reflect → Mutate → Select → Review)
- EvolutionLogger with SQLite audit trail
- SkillLifecycle: versioning, deprecation, retirement
- RollbackManager with archive/restore
- EvolutionHook for AgentRunner integration

### Gateway & WebUI
- FastAPI REST + WebSocket gateway (20+ endpoints)
- React + Vite + TypeScript + Tailwind v3 management console
- Dark Luxury × Bento grid design

### Security
- Shell command whitelist + forbidden pattern detection
- Path traversal prevention with workspace sandboxing
- Secret detection (9 patterns)
- XSS HTML sanitizer

### Documentation
- README with quickstart
- ARCHITECTURE.md with full module design
- CONTRIBUTING.md development guide

---

## v0.8.0 (2026-05-21)

- Evolution engine refinement (logger, lifecycle, rollback, hook)

## v0.7.0 (2026-05-21)

- WebUI management dashboard (React + Vite + Tailwind)

## v0.6.0 (2026-05-21)

- Channel plugin interface + GEPA evolution engine

## v0.5.0 (2026-05-21)

- Multi-workshop runtime management + DAG workflow engine

## v0.4.0 (2026-05-21)

- Kanban monitoring + MCP client + Skill.md management

## v0.3.0 (2026-05-21)

- Memory Tree + TokenJuice + AgentRunner

## v0.2.0 (2026-05-21)

- Core skeleton: OrgEngine, Agent templates, workflow library, warehouse
