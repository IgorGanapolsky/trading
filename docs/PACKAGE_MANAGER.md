# Package-manager honesty

Canonical installer for this repo: **uv** (`uv.lock` + `pyproject.toml`).

Stolen FORMAT from [InfoQ: pnpm 12 Rust rewrite](https://www.infoq.com/news/2026/09/pnpm-12-rust/) (3 Sep 2026):

- Keep the lockfile and command contract; a faster engine is not a migration.
- Unknown / extra lockfiles are errors, not a silent second manager.
- Lifecycle scripts of foreign installers stay default-deny.

**Not stolen:** pnpm itself, Corepack, their 15ms repeated-install or Vercel 64–90% numbers, or rewriting `Makefile` `pip install -e` in this change.

```bash
.venv/bin/python scripts/package_manager_honesty.py
.venv/bin/python scripts/package_manager_honesty.py --classify 'uv sync --frozen'
.venv/bin/python scripts/package_manager_honesty.py --propose-switch pnpm
```

`--propose-switch=pnpm` exits 2. Dual `pnpm-lock.yaml` / `package-lock.json` next to `uv.lock` exits 2.

CI workflows that still `pip install -r requirements-ci.txt` are a **backlog** (frozen-uv migration), not a license to add pnpm.
