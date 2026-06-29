"""Trajectory visualisation (optional extra: ``pip install mnesis-canonical[viz]``).

Plots head-pose translation trajectories for one or more episodes so a demo can
*show* that different capture surfaces emit the same format. Kept out of the
zero-dependency core — matplotlib is imported lazily, with a clear error if the
extra is not installed.
"""
from __future__ import annotations

from pathlib import Path

_DEFAULT_TITLE = "Mnesis Canonical — one format, three capture surfaces"


def _require_pyplot():
    try:
        import matplotlib
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            'visualisation requires matplotlib; install with: '
            'pip install "mnesis-canonical[viz]"'
        ) from e
    matplotlib.use("Agg")  # headless: write PNGs, never open a window
    import matplotlib.pyplot as plt

    return plt


def _label(frames: list[dict]) -> str:
    f = frames[0]
    return f"{f['source.device']} · {f['source.modality']}"


def plot_trajectories(
    episodes: dict[str, list[dict]],
    out_path: str | Path,
    *,
    title: str = _DEFAULT_TITLE,
    dpi: int = 140,
) -> Path:
    """Render head-pose trajectories for ``episodes`` (name -> frames) to a PNG.

    Left panel is the 3D trajectory (vertical axis = canonical ``ty``, ARCore up);
    right panel is the top-down X–Z view. Start = circle, end = square. Returns
    the written path.
    """
    plt = _require_pyplot()
    fig = plt.figure(figsize=(11, 5))
    ax3d = fig.add_subplot(1, 2, 1, projection="3d")
    axtop = fig.add_subplot(1, 2, 2)

    for frames in episodes.values():
        xs = [fr["head_pose_SE3"][0] for fr in frames]
        ys = [fr["head_pose_SE3"][1] for fr in frames]  # vertical (up)
        zs = [fr["head_pose_SE3"][2] for fr in frames]
        label = _label(frames)
        line, = ax3d.plot(xs, zs, ys, label=label)
        color = line.get_color()
        ax3d.scatter([xs[0]], [zs[0]], [ys[0]], color=color, marker="o")
        ax3d.scatter([xs[-1]], [zs[-1]], [ys[-1]], color=color, marker="s")
        axtop.plot(xs, zs, color=color, label=label)
        axtop.scatter([xs[0]], [zs[0]], color=color, marker="o")
        axtop.scatter([xs[-1]], [zs[-1]], color=color, marker="s")

    ax3d.set_xlabel("X (m)")
    ax3d.set_ylabel("Z (m)")
    ax3d.set_zlabel("Y up (m)")
    ax3d.set_title("3D head-pose trajectory")

    axtop.set_xlabel("X (m)")
    axtop.set_ylabel("Z (m)")
    axtop.set_title("Top-down (X–Z)")
    axtop.set_aspect("equal", "datalim")
    axtop.grid(True, alpha=0.3)
    axtop.legend(loc="best", fontsize=8)

    fig.suptitle(title)
    fig.tight_layout()

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi)
    plt.close(fig)
    return out
