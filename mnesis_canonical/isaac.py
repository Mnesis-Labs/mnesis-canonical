"""Isaac Lab / GR00T export adapter — **adapter only, never a wire-format change**.

The Canonical Schema stays exactly as SPEC defines it. This module is a
*reference exporter* for the one convention difference that is unambiguous:

    quaternion order — Canonical is {x,y,z,w} (scalar-last, ARCore);
                       Isaac / USD is {w,x,y,z} (scalar-first).

The reorder is applied to the quaternion block of ``head_pose_SE3`` and
``observation.state`` only. Everything else is passed through untouched.

Still **待对齐 Parthenon `03 §3.2`** (see SPEC §Compatibility) — deliberately NOT
hard-coded here:
  * world frame / up-axis (ARCore Y-up vs Isaac Z-up). Exposed as an optional
    ``world_transform`` hook that defaults to identity — caller supplies the
    transform once the platform fixes it; we do not guess.
  * ``action`` rotation representation (axis-angle vs Isaac action space) — left
    verbatim; do not consume the exported ``action`` as Isaac-native yet.
  * ``source.device`` / ``source.modality`` -> GR00T embodiment tag mapping.

Output frames are "Isaac-flavoured" dicts; they are NOT Canonical-conformant
(the quaternion order differs) and must not be fed back through
``validate_frame`` as if they were canonical. Use :func:`from_isaac` to invert.
"""
from __future__ import annotations

from collections.abc import Callable

_POSE_KEYS = ("head_pose_SE3", "observation.state")


def quat_xyzw_to_wxyz(q: list[float]) -> list[float]:
    """[qx,qy,qz,qw] (scalar-last) -> [qw,qx,qy,qz] (scalar-first)."""
    qx, qy, qz, qw = q
    return [qw, qx, qy, qz]


def quat_wxyz_to_xyzw(q: list[float]) -> list[float]:
    """[qw,qx,qy,qz] (scalar-first) -> [qx,qy,qz,qw] (scalar-last)."""
    qw, qx, qy, qz = q
    return [qx, qy, qz, qw]


def _pose_xyzw_to_wxyz(pose7: list[float]) -> list[float]:
    return list(pose7[:3]) + quat_xyzw_to_wxyz(pose7[3:7])


def _pose_wxyz_to_xyzw(pose7: list[float]) -> list[float]:
    return list(pose7[:3]) + quat_wxyz_to_xyzw(pose7[3:7])


def to_isaac(
    frames: list[dict],
    *,
    reorder_quat: bool = True,
    world_transform: Callable[[list[float]], list[float]] | None = None,
) -> list[dict]:
    """Export canonical frames to Isaac/GR00T-flavoured dicts.

    Quaternions in the pose blocks become scalar-first when ``reorder_quat`` is
    set (default). ``world_transform``, if given, is applied to each pose
    (in canonical ``[tx,ty,tz,qx,qy,qz,qw]`` order) *before* the reorder; it
    defaults to identity because the world-frame alignment is still 待对齐. The
    input frames are not mutated.
    """
    out: list[dict] = []
    for frame in frames:
        f = dict(frame)
        for key in _POSE_KEYS:
            if key not in f:
                continue
            pose = list(f[key])
            if world_transform is not None:
                pose = list(world_transform(pose))
            if reorder_quat:
                pose = _pose_xyzw_to_wxyz(pose)
            f[key] = pose
        out.append(f)
    return out


def from_isaac(
    frames: list[dict],
    *,
    reorder_quat: bool = True,
    world_transform: Callable[[list[float]], list[float]] | None = None,
) -> list[dict]:
    """Invert :func:`to_isaac` back to Canonical frames.

    Undoes the quaternion reorder, then applies ``world_transform`` (which should
    be the inverse of the one passed to :func:`to_isaac`) in canonical order.
    """
    out: list[dict] = []
    for frame in frames:
        f = dict(frame)
        for key in _POSE_KEYS:
            if key not in f:
                continue
            pose = list(f[key])
            if reorder_quat:
                pose = _pose_wxyz_to_xyzw(pose)
            if world_transform is not None:
                pose = list(world_transform(pose))
            f[key] = pose
        out.append(f)
    return out
