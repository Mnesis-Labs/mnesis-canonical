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

## 0. One-time setup (before the *first* release ever)

> 到 2026-08-19 为止**这三项都还没做**，所以 `pip install mnesis-canonical` 至今 404
> （见 #109）。它们需要 PyPI 账号和仓库 admin 权限，worktree 里的 agent 做不了。

- [ ] PyPI 上占下 `mnesis-canonical` 这个名字（现在是 404，未被占用）。
- [ ] 生成 scope 到该项目的 API token，存成仓库/组织 secret **`PYPI_TOKEN`**
      （Settings → Secrets and variables → Actions）。
      `.github/workflows/release.yml` 第一步就断言它非空，缺了会在 5 秒内红掉，
      不会留下「Release 建好了但包没上」的半成品。
- [ ] 确认自托管 runner 能连 `upload.pypi.org`（本仓 pip 走国内镜像，
      **上传走的是官方源**，是另一条出口路径）。

## 7. Git & tag

> 🧊 **2026-08-20：PyPI 发布已冷冻**（Muso 原话「PyPI直接冷冻，现阶段都不考虑发布」）。
> 本节与 §8 描述的是**解冻后**的流程，现阶段不要执行。
>
> ⚠️ **一个版本号只有一次机会**。PyPI 上一个版本号传上去就不能重传，删掉也不能复用。
> **要发布就发一个新版本号**，别试图复活旧 tag。
>
> 历史注记：v0.5.0 的 tag 打在 07-28 的提交上，早于 workflow 本身落地（#98，08-09）；
> 当时 `release.yml` 由推 tag 触发而**已存在的 tag 再推是 no-op**，所以那条链路一次
> 都没跑过。**2026-08-20 起触发方式已改为手动**（见下），旧 tag 的这个限制不再适用，
> 但「版本号不可重传」依旧成立。

- [ ] All changes committed on `main`.
- [ ] Tag: `git tag -a v<version> -m "v<version>"` —— 版本号必须与 §1 的三处字符串
      一致，workflow 的 `Tag matches package version` 一步会当场比对。
- [ ] Push: `git push origin main --tags`.
- [ ] **推 tag 不会自动发布**（2026-08-20 起）。发布要显式派发：
      `gh workflow run release.yml --ref v<version>` —— `--ref` 必须指向那个 tag，
      workflow 第一步 `Dispatch target must be a version tag` 会校验 ref 类型与命名，
      随后 `Tag matches package version` 再比对 tag 名与树里的版本号。

## 8. GitHub Release + PyPI

`release.yml` 被**手动派发**后做完本节（2026-08-20 起不再由推 tag 自动触发），顺序是**先 PyPI 后 Release**：
包真的能装了才对外宣布，避免再次产生「ROADMAP 说发了、产物不在」的假象。

- [ ] `twine check` + `twine upload` → 包出现在 https://pypi.org/project/mnesis-canonical/。
- [ ] Release 自动从 `CHANGELOG.md` 的 `## [x.y.z]` 段落取 notes，附 `sdist` / `wheel`。
- [ ] **验收就一行**（不看 workflow 绿不绿，看产物）：
      `pip install mnesis-canonical==<version>` 在一个干净 venv 里能装上并 import。

---

*See `CONTRACTS.md` for the cross-repo contract registry and `CLAUDE.md` for
worker discipline.*