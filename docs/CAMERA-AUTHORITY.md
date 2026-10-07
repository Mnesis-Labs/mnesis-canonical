# C9 camera authority — camera-authority/1.0 (candidate, 2026-10-08)

Owner: canonical. Producers: Eidolon/Iris. Consumers: Ambrosia reconstruction;
Daedalus only when it explicitly adopts the same authority. This is the existing
C9 work item, not a new feature. Contract schema:
[`camera_authority.schema.json`](../mnesis_canonical/contracts/camera_authority.schema.json).
Reference validator: [`camera_authority.py`](../mnesis_canonical/camera_authority.py).
CPU acceptance: [`test_camera_authority.py`](../tests/test_camera_authority.py).

## Authority and compatibility

This standalone, canonical-owned per-image record has its own version
`camera-authority/1.0`. It is NOT inserted into C1 or the strict C2b inventory;
neither older contract changes meaning. An adopter must pin the new source and
schema hash and supply this record explicitly. No upload field/endpoint, SDK,
consumer implementation, top-level export or package release is introduced here.

Base local HEAD `1a75546c8330a8273f360aef5f727389a3ada0bd` defines the accepted
0.6.1 C1/C2b spec; tree `f3d4169ed4eef71bf2d01e1e7c81e26945c3a564` matches the
previously accepted merged source `d239d3588daba8d61f1f395921d9805cf01049c2`.
The already accepted d239 wheel SHA256
`6d5341259c37b5cae03b321a79b9637b8ef7d89de8c3bc2e093efbc5c6784de6`
does NOT contain this new contract. These merged-source/wheel facts are recorded
in Parthenon's RECOVERY-20261003; this batch does not re-fetch, rebuild, install,
upgrade a consumer or claim post-merge CI. Same package version is not compatibility.

## Geometry: preserve true head, derive sensor

Use column vectors and right-handed metric coordinates. Every pose is
`[tx,ty,tz,qx,qy,qz,qw]`, unit quaternion scalar-last. The calibration maps sensor
coordinates into head coordinates; head pose maps head into the named world:

`T_world_sensor = T_world_head_at_exposure * T_head_sensor`.

Intrinsics describe the actual image's **undistorted pinhole** pixels, row-major
`K=[fx,0,cx,0,fy,cy,0,0,1]`, with positive fx/fy and explicit width/height.
Sensor optical coordinates are +x right, +y down, +z forward. Head frame axes
must be identified by the calibration. Unity/SDK handedness conversion must be
proven before producing canonical poses, not guessed from a provider name.
Distorted/raw geometry is unsupported in this version: reject it, do not relabel
it as rectified. This contract does not implement rectification or rolling-shutter
correction; consumer suitability checks remain required.

Nonidentity calibration is supported; it is not an error or a reason to replace
`head_pose_SE3` with camera pose. The C1 row keeps its actual head pose. A camera
may expose at a different time from the reference row, especially in multicam:
`head_pose_at_exposure` is a separate measured/interpolated head pose, not a rewrite
of the C1 row. Never copy sensor into head to satisfy an old exporter. Missing
extrinsics are NOT identity. Explicit identity needs the same calibration receipt
as nonidentity, and must match independent consumer-verified calibration contents.

The checked synthetic sample has head translation (1,2,3), head rotation +90° Z,
head→sensor translation (.1,0,0), head→sensor rotation +90° Y. Result:
`[1,2.1,3,-.5,.5,.5,.5]`; head is unchanged. q/-q equivalence is accepted;
nonunit/huge/nonfinite quaternions are rejected, not normalized.

## Exposure time and evidence

Exposure time is **exposure midpoint**, never host receive/callback time.
`clock_mapping` explicitly names camera source and head target clock namespaces:
`head_pose_at_exposure.time_ns = exposure.time_ns + offset_ns`.
The offset direction is fixed. The pose must be sampled/interpolated at that
mapped exposure time; using a current/stale head sample is invalid. Mapping
uncertainty must be at most the caller's explicit `max_clock_error_ns` policy;
missing policy is not zero and is not ready. C6 episode-level clock metadata is
not a substitute for this per-exposure mapping. Same-clock mapping still needs
evidence and must use offset zero. This version models a fixed-offset mapping;
clock drift requires a renewed evidence-valid mapping, not indefinite reuse.

Provider id/version, exposure, head pose, clock mapping and calibration each
carry named evidence bindings. Calibration has sensor/head IDs, immutable
revision and evidence SHA256; intrinsics identify that same calibration/revision.
World IDs must agree; none of these IDs are inferred from array length or device
type. Missing K/clock/calibration/evidence blocks authority. A string/hash supplied
by a producer alone is not proof that the file exists or that its content matches.

`validate_camera_authority` checks schema and cross-field composition/time only.
`validate_camera_authority_binding` additionally validates the C1 row and joins
upload episode identity, frame index, image key/ref, independently measured image
SHA256, calibration revision/hash/**actual decoded K and T_head_sensor**, and
provider id/version. Consumers MUST verify image bytes/geometry/dimensions, load
and hash the actual immutable calibration and provider/clock/head/exposure receipts,
validate their provenance and validity interval, then pass independently decoded
values; do not echo record claims back as the "verified" arguments. These functions
do not open evidence paths, inspect devices or grant reconstruction readiness.
Clock drift, provider receipt validity, exposure duration and physical calibration
accuracy remain independent runtime checks, not inferred from schema success.

## Fixture and acceptance boundary

[`nonidentity.fixture.json`](../examples/camera_authority/nonidentity.fixture.json)
contains the same authority sample and a current-schema C1 ego fixture. All
receipts are synthetic and explicitly `fixture:true`; no actual JPEG exists.
`allow_fixture=True` is CPU-test-only. Default validation and composition reject
fixture evidence. Clearing a flag does not prove real acquisition; validators are
not cryptographic provenance oracles. Unknown/queued/fixture/old APK cannot turn
the MR acceptance manifest green.

CPU negatives cover missing prerequisites, stale/inverted clock, excessive clock
error, identity fabrication/composition mismatch, mismatched calibration revision
and independently verified hash/pose/K, foreign world/sensor/image/provider/version,
invalid C1/image key, booleans/nonfinite/huge pose numbers and forbidden version.
They prove deterministic contract behavior only. ED actual producer fixtures and
AM consumer/exposure-time reconstruction/export adoption are **NOT_TESTED** here.
No service, native engine, Unity, SDK, device, training, install or release is run.
