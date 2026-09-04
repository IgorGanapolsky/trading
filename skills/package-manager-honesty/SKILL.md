---
name: package-manager-honesty
description: >
  Fail-closed uv.lock doctor. Steal InfoQ pnpm 12 FORMAT (keep lockfile, refuse
  manager switch, unknown extra lockfiles). Do not migrate trading to pnpm.
  Slash: /package-manager-honesty.
---

# Package-manager honesty (trading)

## Do

```bash
.venv/bin/python scripts/package_manager_honesty.py
.venv/bin/python scripts/package_manager_honesty.py --propose-switch pnpm
```

Canonical: `uv.lock`. Foreign lockfiles (`pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`, `bun.lock*`) fail closed.

## Never

- Add a second lockfile
- Cite pnpm 15ms / Vercel 64–90% as our numbers
- Rewrite GitHub Actions to pnpm
- Dual-edit AGENT-573 / AGENT-574 files
