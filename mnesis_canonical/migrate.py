"""One-shot migrations for data produced before a field was standardised.

The standard itself only ever accepts the canonical names — aliases in an open
standard never die, so the validator does **not** recognise legacy keys.  Instead
producers rewrite their stockpiled episodes once, with the functions here.

Currently one migration:

``hand_v0`` — the four pre-C11 hand fields that Mnesis-Iris emitted from D-13
onwards, before hand keypoints were standardised (Parthenon#47):

===============================  ==========================================
legacy key                       canonical key
===============================  ==========================================
``hand_left_kpts3d``   float[63] ``observation.hand.left``
``hand_right_kpts3d``  float[63] ``observation.hand.right``
``hand_kpts_source``   str       ``observation.hand.source``
``hand_pose``          float[128] *dropped* — derived, and encodes absence
                                 as in-band zeros (see SPEC §Conventions)
===============================  ==========================================

plus the two keys that make the block self-describing and that the legacy data
never carried: ``observation.hand.layout`` (``mediapipe_hand_21``) and
``observation.hand.frame`` (``head_anchored`` — the machine-readable form of the
2.5D caveat that used to live only in a Kotlin class comment).
"""
from __future__ import annotations

from .schema import HAND_FRAME_KEY, HAND_FRAMES, HAND_LAYOUT_KEY, HAND_SOURCE_KEY

# Legacy key -> canonical key.  ``hand_pose`` is absent on purpose: it is a
# derived projection of the other two and belongs to the LeRobot exporter, not
# the wire format.
HAND_V0_RENAMES = {
    "hand_left_kpts3d": "observation.hand.left",
    "hand_right_kpts3d": "observation.hand.right",
    "hand_kpts_source": HAND_SOURCE_KEY,
}

# Dropped outright by the migration (derived / re-derivable at export time).
HAND_V0_DROPPED = ("hand_pose",)

# What the legacy producer actually meant, made explicit.
HAND_V0_LAYOUT = "mediapipe_hand_21"
HAND_V0_FRAME = "head_anchored"


def migrate_hand_v0(
    frame: dict,
    *,
    layout: str = HAND_V0_LAYOUT,
    reference_frame: str = HAND_V0_FRAME,
) -> dict:
    """Return a copy of ``frame`` with the pre-C11 hand fields rewritten.

    Frames that carry none of the legacy keys are returned unchanged (as a
    shallow copy), so this is safe to run over a whole mixed corpus.

    Args:
        frame: One canonical frame dict.
        layout: Skeleton layout id to declare. The default matches what the
            legacy fields always were (21 MediaPipe landmarks x 3).
        reference_frame: Value for ``observation.hand.frame``; one of
            :data:`mnesis_canonical.schema.HAND_FRAMES`. The default records
            that the points are metric and self-consistent within the hand but
            **not** localised in the world.

    Raises:
        ValueError: If ``reference_frame`` is not a recognised frame value.
    """
    if reference_frame not in HAND_FRAMES:
        raise ValueError(
            f"reference_frame must be one of {HAND_FRAMES}, got {reference_frame!r}"
        )

    out = dict(frame)
    touched = False

    for legacy, canonical in HAND_V0_RENAMES.items():
        if legacy in out:
            out[canonical] = out.pop(legacy)
            touched = True

    for legacy in HAND_V0_DROPPED:
        if legacy in out:
            del out[legacy]
            touched = True

    if not touched:
        return out

    # Only declare layout/frame when actual keypoints survived the rewrite: a
    # frame that carried nothing but hand_pose has no keypoints to describe.
    has_kpts = any(
        key in out for key in ("observation.hand.left", "observation.hand.right")
    )
    if has_kpts:
        out.setdefault(HAND_LAYOUT_KEY, layout)
        out.setdefault(HAND_FRAME_KEY, reference_frame)
    return out


def migrate_hand_v0_frames(
    frames: list[dict],
    *,
    layout: str = HAND_V0_LAYOUT,
    reference_frame: str = HAND_V0_FRAME,
) -> list[dict]:
    """Apply :func:`migrate_hand_v0` to every frame of an episode."""
    return [
        migrate_hand_v0(f, layout=layout, reference_frame=reference_frame)
        for f in frames
    ]
