# Contributing to AI Factory

## Getting Started

```bash
git clone <repo-url>
cd ai-factory
pip install -e ".[dev]"
python3 -m pytest factory/ gateway/ -v
```

## Development Workflow

1. **Plan first** — discuss the approach before writing code
2. **TDD** — write tests first, then implement (80%+ coverage)
3. **Code review** — all changes reviewed before merge
4. **Conventional commits** — `feat:`, `fix:`, `refactor:`, `docs:`, `test:`

## Project Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full module design.

## Testing

```bash
python3 -m pytest factory/ gateway/ -v    # Full suite (314 tests)
python3 -m pytest factory/kanban/ -v      # Specific module
```

## Code Style

- Python: PEP 8, type annotations, frozen dataclasses
- TypeScript: strict mode, interfaces over types, no `any`
- CSS: Tailwind utility classes, custom theme tokens

## Questions

Open an issue or start a discussion.
