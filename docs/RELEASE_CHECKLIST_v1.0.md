# Release Checklist v1.0

Pre-release walkthrough for `mnesis-canonical`.  Run through these steps **in
order** before tagging a release.

---

## 1. Version bump

Bump all three strings to the same value — `python scripts/version_check.py`
(also run as `release_check.py --only version`) fails the release if they differ:

- [ ] `mnesis_canonical/__init__.py` — `__version__` string.
- [ ] `pyproject.toml` — `[project] version` field.
- [ ] `CHANGELOG.md` preamble — the `**Package x.y.z**` line.

Manual (not machine-checkable):

- [ ] `CHANGELOG.md` — move [Unreleased] entries under the new version heading,
      add the `[x.y.z]:` comparison link at the bottom.

## 2. Contracts integrity

> 本节由 `scripts/release_check.py` 自动校验（CI job `Release checklist §2-§6`）。
> 局部跑：`python scripts/release_check.py --only contracts`。

- [ ] `python -m mnesis_canonical.contracts_check` — passes (exit 0).
- [ ] If contracts changed: `contracts/contracts.lock` regenerated, PM
      `type:contract-change` process followed.

## 3. Embodiment registry

> 本节由 `scripts/release_check.py` 自动校验（`--only embodiments`）。

- [ ] `python -m mnesis_canonical.embodiment_check` — passes (exit 0).
- [ ] All `embodiments/*.json` files validate against `embodiment.schema.json`.

## 4. Lint & type check

> 本节由 `scripts/release_check.py` 自动校验（`--only lint`）。

- [ ] `ruff check .` — no errors.
- [ ] `pyright .` — zero type errors (if `pyright` is available in dev deps).

## 5. Tests

> 本节由 `scripts/release_check.py` 自动校验（`--only tests`）。

- [ ] `pytest -q` — all tests pass.
- [ ] `pytest -q -m slow` — slow tests pass (if any).

## 6. Manual smoke tests

> 本节由 `scripts/release_check.py` 自动校验（`--only smoke`）。

- [ ] `python -m mnesis_canonical --help` — prints help.
- [ ] `python -m mnesis_canonical validate examples/episode_0/data.jsonl` — OK.
- [ ] `python -m mnesis_canonical.importers --help` — prints help.
- [ ] `python -m mnesis_canonical.importers list` — lists registered importers.

## 7. Git & tag

- [ ] All changes committed on `main`.
- [ ] Tag: `git tag -a v<version> -m "v<version>"`.
- [ ] Push: `git push origin main --tags`.

## 8. GitHub Release + PyPI

Automated by `.github/workflows/release.yml` — pushing the tag runs the version
guard, §2–§6, the build, `twine check --strict`, a clean-venv install of the
built wheel, then creates the Release and publishes to PyPI.

- [ ] `release.yml` finished green for this tag.
- [ ] `pip install mnesis-canonical==<version>` works from a clean environment.

Re-publishing a tag that already exists (workflow landed after the tag):
`gh workflow run release.yml -f tag=v<version> -f dry_run=true` first, then
without `dry_run`. PyPI uploads cannot be overwritten, only yanked.

One-time setup — PyPI Trusted Publishing, no `PYPI_TOKEN` secret: see
`DEV_GUIDE.md` §5 §9.

---

*See `CONTRACTS.md` for the cross-repo contract registry and `CLAUDE.md` for
worker discipline.*