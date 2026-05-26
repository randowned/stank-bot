---
description: Run the full validation suite — lint, typecheck, migration chain, unit tests, frontend checks, and E2E tests.
---

Run each validation step in order. Report pass/fail per step. Stop on the first failure unless `--all` is passed as an argument.

## Steps

### 1. Lint (ruff)
```bash
ruff check src tests
```
Report any violations. Fail if exit code is non-zero.

### 2. Type check (mypy)
```bash
mypy src --ignore-missing-imports
```
Report any type errors. Fail if exit code is non-zero.

### 3. Migration chain integrity
```bash
alembic history
```
Verify the chain is linear (no forks, no missing revisions). Fail if alembic reports errors.

### 4. Unit tests
```bash
pytest tests/unit/ -x --tb=short
```
Report pass/fail count. Fail if any test fails.

### 5. Frontend type check
```bash
cd src/stankbot/web/frontend && npm run check
```
Report any Svelte/TypeScript errors. Fail if exit code is non-zero.

### 6. E2E tests
Skip this step if `--fast` was passed as an argument.
```bash
node scripts/run-e2e.mjs
```
Report pass/fail count. Fail if any test fails.

### 7. Summary
Print a table of all steps with pass/fail status. Example:

```
Step                 Status
─────────────────────────────
Lint (ruff)          ✓ pass
Type check (mypy)    ✓ pass
Migration chain      ✓ pass
Unit tests           ✓ pass (24 passed)
Frontend checks      ✓ pass
E2E tests            ✓ pass (142 passed)
```
