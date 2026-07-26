# Release Checklist v1.0

Pre-release walkthrough for `mnesis-canonical`.  Run through these steps **in
order** before tagging a release.

---

## 1. Version bump

- [ ] `mnesis_canonical/__init__.py` — `__version__` string.
- [ ] `pyproject.toml` — `[project] version` field.
- [ ] `CHANGELOG.md` — move [Unreleased] entries under the new version heading,
      add the `[x.y.z]:` comparison link at the bottom.

## 2. Contracts integrity

- [ ] `python -m mnesis_canonical.contracts_check` — passes (exit 0).
- [ ] If contracts changed: `contracts/contracts.lock` regenerated, PM
      `type:contract-change` process followed.

## 3. Embodiment registry

- [ ] `python -m mnesis_canonical.embodiment_check` — passes (exit 0).
- [ ] All `embodiments/*.json` files validate against `embodiment.schema.json`.

## 4. Lint & type check

- [ ] `ruff check .` — no errors.
- [ ] `pyright .` — zero type errors (if `pyright` is available in dev deps).

## 5. Tests

- [ ] `pytest -q` — all tests pass.
- [ ] `pytest -q -m slow` — slow tests pass (if any).

## 6. Manual smoke tests

- [ ] `python -m mnesis_canonical --help` — prints help.
- [ ] `python -m mnesis_canonical validate examples/episode_0/data.jsonl` — OK.
- [ ] `python -m mnesis_canonical.importers --help` — prints help.
- [ ] `python -m mnesis_canonical.importers list` — lists registered importers.

## 7. Git & tag

- [ ] All changes committed on `main`.
- [ ] Tag: `git tag -a v<version> -m "v<version>"`.
- [ ] Push: `git push origin main --tags`.

## 8. GitHub Release

- [ ] Create a Release from the tag with changelog notes.
- [ ] Attach `sdist` / `wheel` (if publishing to PyPI).

---

*See `CONTRACTS.md` for the cross-repo contract registry and `CLAUDE.md` for
worker discipline.*