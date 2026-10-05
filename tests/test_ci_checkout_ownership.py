"""Exercise the workflow's actual bootstrap shell against owned local Git repos."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
JOBS = ("test", "contracts-check", "embodiment-check", "release-check")


def checkout_scripts():
    text = WORKFLOW.read_text(encoding="utf-8")
    blocks = re.findall(r"      - name: Checkout\n.*?        run: \|\n(.*?)(?=      -)", text, re.S)
    assert len(blocks) == len(JOBS)
    return ["\n".join(line[10:] for line in block.splitlines()) + "\n" for block in blocks]


def test_checkout_uses_owned_temp_without_destructive_workspace_commands():
    for script in checkout_scripts():
        assert "mktemp -d" in script and "RUNNER_TEMP" in script
        assert "git clean" not in script and "git reset" not in script
        assert script.index('cd "$owned"') < script.index("git init -q .")
        assert "GITHUB_SHA" in script and "rev-parse HEAD" in script
        assert "for n in" not in script and "sleep " not in script


GIT = "C:/Program Files/Git/cmd/git.exe" if os.name == "nt" else "git"
BASH = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else "bash"


def local_env(root):
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
    }
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=str(root / "empty-config"),
        GIT_TERMINAL_PROMPT="0",
        GIT_ALLOW_PROTOCOL="file",
    )
    return env


def git(repo, *args):
    proc = subprocess.run(
        [GIT, "-C", str(repo), *args],
        env=local_env(repo),
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    return proc.stdout.strip()


def init_repo(repo, content):
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "--local", "user.name", "Offline CI fixture")
    git(repo, "config", "--local", "user.email", "fixture@example.invalid")
    (repo / "tracked.txt").write_text(content, encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-qm", "owned fixture")
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def local_root(tmp_path_factory):
    # Short owned basename avoids Windows MAX_PATH in synthetic .git objects.
    return tmp_path_factory.mktemp("c")


def execute_checkout(root, script, sha=None, inherited=None, wrong_head=False, config_route=None):
    server = root / "local-server"
    source = server / "fixture/repo"
    target = init_repo(source, "fixed source commit\n")
    workspace = root / "stale-workspace"
    stale_head = init_repo(workspace, "old tracked file\n")
    (workspace / "unknown-user.bin").write_bytes(b"preserve unknown user data")
    temp = root / "r t"
    temp.mkdir()
    env_file = root / "github-env.txt"
    output = root / "github-output.txt"
    env_file.touch()
    output.touch()
    env = local_env(root)
    env.update(
        RUNNER_TEMP=str(temp),
        GITHUB_ENV=str(env_file),
        GITHUB_OUTPUT=str(output),
        GITHUB_SERVER_URL=server.as_posix(),
        GITHUB_REPOSITORY="fixture/repo",
        GITHUB_SHA=sha or target,
    )
    if inherited:
        env.update(GIT_DIR=(workspace / ".git").as_posix(), GIT_WORK_TREE=workspace.as_posix())
    if config_route == "count":
        env.update(
            GIT_CONFIG_COUNT="1",
            GIT_CONFIG_KEY_0="core.worktree",
            GIT_CONFIG_VALUE_0=workspace.as_posix(),
        )
    if config_route == "parameters":
        env["GIT_CONFIG_PARAMETERS"] = f"'core.worktree={workspace.as_posix()}'"
    if config_route:
        injected = subprocess.run(
            [GIT, "-C", str(workspace), "config", "--get", "core.worktree"],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert injected.returncode == 0 and injected.stdout.strip() == workspace.as_posix()
    if wrong_head:
        # Fault injection changes actual owned checkout HEAD after real Git checkout.
        # It is not a GitHub transport simulation or a fake successful execution.
        bin_dir = root / "fault-bin"
        bin_dir.mkdir()
        wrapper = bin_dir / "git"
        real_git_location = shutil.which(GIT)
        assert real_git_location is not None, f"Git fixture executable not found: {GIT}"
        real_git = Path(real_git_location).as_posix()
        wrapper.write_text(
            "#!/bin/bash\nset -e\n"
            f'"{real_git}" "$@"\n'
            'if [[ "$1" == checkout ]]; then\n'
            f'  "{real_git}" -c user.name=Fixture -c user.email=fixture@example.invalid '
            "commit --allow-empty -qm unexpected-head\nfi\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o700)
        bootstrap = root / "fault-bash-env"
        path = bin_dir.as_posix()
        line = (
            f"fault_path=\"$(cygpath -u '{path}')\"\n"
            if os.name == "nt"
            else f"fault_path='{path}'\n"
        )
        bootstrap.write_text(line + 'export PATH="$fault_path:$PATH"\nhash -r\n', encoding="utf-8")
        env["BASH_ENV"] = str(bootstrap)
    env["GITHUB_TOKEN"] = "synthetic-token-sentinel-never-real"
    shell = root / "actual-checkout.sh"
    shell.write_text(script, encoding="utf-8")
    proc = subprocess.run(
        [BASH, "--noprofile", "--norc", "-eo", "pipefail", str(shell)],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    (root / "actual-checkout-result.json").write_text(
        json.dumps(
            {
                "argv": proc.args,
                "exit": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "target_sha": target,
                "stale_sha": stale_head,
                "note": (
                    "Only actual Git operations in owned local fixtures; "
                    # Keep this note wrapped without changing executed test semantics.
                    "no network/GitHub runner."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return proc, workspace, stale_head, env_file, output, temp, target


def test_inherited_git_environment_cannot_redirect_checkout_into_stale_tree(local_root):
    proc, workspace, stale_head, env_file, _, _, _ = execute_checkout(
        local_root, checkout_scripts()[0], inherited=True
    )
    assert git(workspace, "rev-parse", "HEAD") == stale_head
    assert (workspace / "tracked.txt").read_text(encoding="utf-8") == "old tracked file\n"
    assert (workspace / "unknown-user.bin").read_bytes() == b"preserve unknown user data"
    assert proc.returncode == 0, proc.stderr
    assert env_file.read_text(encoding="utf-8").startswith("CI_CHECKOUT_DIR=")


def test_checkout_preserves_runner_auth_without_inline_token_or_interaction():
    for script in checkout_scripts():
        assert "credential.helper=" not in script
        assert "GIT_TERMINAL_PROMPT=0" in script
        assert "extraheader" not in script and "GITHUB_TOKEN" not in script
        assert "git config --global" not in script


@pytest.mark.parametrize("config_route", ["count", "parameters"])
def test_config_injection_cannot_redirect_checkout_into_stale_tree(local_root, config_route):
    proc, workspace, stale_head, env_file, _, _, _ = execute_checkout(
        local_root, checkout_scripts()[0], config_route=config_route
    )
    assert (workspace / "tracked.txt").read_text(encoding="utf-8") == "old tracked file\n"
    assert (workspace / "unknown-user.bin").read_bytes() == b"preserve unknown user data"
    assert git(workspace, "rev-parse", "HEAD") == stale_head
    assert proc.returncode == 0, proc.stderr
    assert env_file.read_text(encoding="utf-8").startswith("CI_CHECKOUT_DIR=")


def test_all_config_injection_variables_are_explicitly_cleared():
    for script in checkout_scripts():
        assert "unset GIT_CONFIG GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT" in script
        assert "${!GIT_CONFIG_KEY_@}" in script and "${!GIT_CONFIG_VALUE_@}" in script
        assert 'unset "$name"' in script


@pytest.mark.parametrize("job", range(4), ids=JOBS)
def test_actual_job_checkout_preserves_stale_files_and_publishes_fixed_head(local_root, job):
    proc, workspace, stale_head, env_file, output, temp, target = execute_checkout(
        local_root, checkout_scripts()[job]
    )
    assert proc.returncode == 0, proc.stderr
    assert git(workspace, "rev-parse", "HEAD") == stale_head
    assert (workspace / "tracked.txt").read_text(encoding="utf-8") == "old tracked file\n"
    assert (workspace / "unknown-user.bin").read_bytes() == b"preserve unknown user data"
    env_line = env_file.read_text(encoding="utf-8").splitlines()
    output_line = output.read_text(encoding="utf-8").splitlines()
    assert len(env_line) == len(output_line) == 1
    checkout = Path(env_line[0].removeprefix("CI_CHECKOUT_DIR="))
    assert checkout.resolve().is_relative_to(temp.resolve())
    assert output_line[0] == "checkout_dir=" + checkout.as_posix()
    assert git(checkout, "rev-parse", "HEAD") == target
    assert (checkout / "tracked.txt").read_text(encoding="utf-8") == "fixed source commit\n"
    assert "synthetic-token-sentinel-never-real" not in proc.stdout + proc.stderr
    assert "synthetic-token-sentinel-never-real" not in (checkout / ".git/config").read_text()


@pytest.mark.parametrize("sha", ["main", "abc123", "1" * 40 + "\nCI_CHECKOUT_DIR=evil"])
def test_invalid_or_injected_sha_fails_before_creating_checkout(local_root, sha):
    proc, workspace, stale_head, env_file, output, temp, _ = execute_checkout(
        local_root, checkout_scripts()[0], sha=sha
    )
    assert proc.returncode == 2
    assert list(temp.iterdir()) == []
    assert env_file.read_text() == output.read_text() == ""
    assert git(workspace, "rev-parse", "HEAD") == stale_head


def test_unavailable_full_sha_fetch_stays_nonzero_without_outputs(local_root):
    proc, workspace, stale_head, env_file, output, temp, _ = execute_checkout(
        local_root, checkout_scripts()[0], sha="0" * 40
    )
    assert proc.returncode != 0
    assert env_file.read_text() == output.read_text() == ""
    assert git(workspace, "rev-parse", "HEAD") == stale_head
    assert len(list(temp.iterdir())) == 1  # Failed owned evidence retained, not cleaned.


def test_actual_wrong_head_is_refused_and_never_published(local_root):
    proc, workspace, stale_head, env_file, output, temp, target = execute_checkout(
        local_root, checkout_scripts()[0], wrong_head=True
    )
    assert proc.returncode == 3, proc.stderr
    assert env_file.read_text() == output.read_text() == ""
    assert git(workspace, "rev-parse", "HEAD") == stale_head
    checkouts = list(temp.iterdir())
    assert len(checkouts) == 1 and git(checkouts[0], "rev-parse", "HEAD") != target


def test_new_job_checkouts_cannot_reuse_each_others_directory(local_root):
    # Shared runner temp across two actual job bootstraps; no preselected destination.
    proc, _, _, env_file, output, temp, _ = execute_checkout(local_root, checkout_scripts()[0])
    assert proc.returncode == 0, proc.stderr
    first = env_file.read_text()
    env = local_env(local_root)
    env.update(
        RUNNER_TEMP=str(temp),
        GITHUB_ENV=str(env_file),
        GITHUB_OUTPUT=str(output),
        GITHUB_SERVER_URL=(local_root / "local-server").as_posix(),
        GITHUB_REPOSITORY="fixture/repo",
        GITHUB_SHA=git(local_root / "local-server/fixture/repo", "rev-parse", "HEAD"),
    )
    shell = local_root / "second-job.sh"
    shell.write_text(checkout_scripts()[1], encoding="utf-8")
    second = subprocess.run(
        [BASH, "--noprofile", "--norc", "-eo", "pipefail", str(shell)],
        cwd=local_root / "stale-workspace",
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert second.returncode == 0, second.stderr
    published = env_file.read_text().splitlines()
    assert len(published) == 2 and published[0] != published[1]
    assert first.strip() == published[0] and len(list(temp.iterdir())) == 2


def test_all_followup_commands_explicitly_use_new_checkout():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("id: checkout") == 4
    assert text.count("working-directory: ${{ github.workspace }}") == 4
    for command in re.finditer(r"      - run: (uv .+)\n([^\n]+)", text):
        assert command.group(2).strip() == "working-directory: ${{ env.CI_CHECKOUT_DIR }}"
    assert text.count("working-directory: ${{ env.CI_CHECKOUT_DIR }}") == 14
    assert (
        "--ignore=tests/test_isaac.py --ignore=tests/test_objects_jsonl.py "
        "--ignore=tests/test_sdk.py"
    ) in text
    assert 'branches: ["**"]' in text and "cancel-in-progress:" in text
