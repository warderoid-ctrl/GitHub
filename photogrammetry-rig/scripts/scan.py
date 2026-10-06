"""Turn folders of photos into dense point clouds, headlessly.

    python scripts/scan.py                 # every object in input/ that has no output yet
    python scripts/scan.py mug             # just input/mug
    python scripts/scan.py mug -q high     # with a quality preset
    python scripts/scan.py --list          # what is queued
    python scripts/scan.py --doctor        # check the install before a long run

Each object is a subfolder of input/. Results land in output/<object>/, and the
(large) intermediate cache lives in work/<object>/.
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
import time
from pathlib import Path

from rig import (
    DEFAULT_PRESET, INPUT_DIR, OUTPUT_DIR, PRESETS, WORK_DIR,
    RigError, build_env, find_executable, find_meshroom_root, gpu_summary,
    list_images, list_objects, meshroom_batch_cmd,
)

# Node the pipeline stops at. Meshing is what fuses the filtered depth maps into
# the dense cloud, so it is required even though we discard the mesh itself.
# Named exactly as the template declares it, since --toNode prefix-matches.
TARGET_NODE = "Meshing_1"


def log(msg: str = "") -> None:
    print(msg, flush=True)


def run_streaming(cmd: list[str], logfile: Path, env: dict[str, str] | None = None) -> int:
    """Run a command, echoing output live and tee-ing it to ``logfile``."""
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open("a", encoding="utf-8", errors="replace") as handle:
        handle.write(f"\n$ {' '.join(cmd)}\n")
        handle.flush()
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1, env=env,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            handle.write(line)
        return proc.wait()


def find_dense_cloud(cache: Path) -> Path | None:
    """Locate the dense point cloud the Meshing node wrote.

    Meshroom lays the cache out as ``<cache>/<NodeName>/<uid>/<files>``, but the
    exact filename has varied across releases, so probe by preference order and
    fall back to any .abc under a Meshing folder. The newest match wins, which
    matters when a node has been recomputed.
    """
    meshing_dirs = [p for p in cache.glob("**/Meshing*/*") if p.is_dir()]
    if not meshing_dirs:
        return None

    for filename in ("densePointCloud.abc", "densePointCloud_raw.abc"):
        hits = [d / filename for d in meshing_dirs if (d / filename).is_file()]
        if hits:
            return max(hits, key=lambda p: p.stat().st_mtime)

    hits = [p for d in meshing_dirs for p in d.glob("*.abc")]
    return max(hits, key=lambda p: p.stat().st_mtime) if hits else None


def ply_vertex_count(path: Path) -> int:
    """Read the vertex count out of a PLY header, or -1 if it isn't a PLY."""
    with path.open("rb") as handle:
        for _ in range(64):
            line = handle.readline()
            if not line or line.strip() == b"end_header":
                break
            if line.startswith(b"element vertex"):
                return int(line.split()[2])
    return -1


def strip_camera_markers(path: Path, n_views: int) -> None:
    """Drop the camera-position markers exportColoredPointCloud prepends.

    The exporter has no flag to omit them: it writes one pure-green (0,255,0)
    vertex per registered camera ahead of the actual cloud. They sit well away
    from the object and skew auto-scaling in most viewers.

    Only the first ``n_views`` vertices are considered, and only if every one of
    them is pure green — otherwise the file is left exactly as it was, so a green
    object can never lose real points to this.
    """
    if n_views <= 0:
        return

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        header: list[str] = []
        for line in handle:
            header.append(line)
            if line.strip() == "end_header":
                break
        else:
            return  # no end_header; not something we should rewrite

        candidates = [handle.readline() for _ in range(n_views)]
        if not all(c.rstrip().endswith("0 255 0") for c in candidates if c):
            return

        total = next(
            (int(h.split()[2]) for h in header if h.startswith("element vertex")), -1
        )
        if total < 0:
            return

        tmp = path.with_suffix(".ply.tmp")
        with tmp.open("w", encoding="utf-8", newline="") as out:
            for h in header:
                if h.startswith("element vertex"):
                    h = f"element vertex {total - n_views}\n"
                out.write(h)
            shutil.copyfileobj(handle, out)

    tmp.replace(path)


def export_point_cloud(meshroom_root: Path, source: Path, dest: Path,
                       logfile: Path, n_views: int) -> int:
    """Export the dense .abc as a coloured .ply. Returns the vertex count, or -1.

    convertSfMFormat is the wrong tool here: it reads the dense cloud's landmarks
    as empty and silently emits a header-only file containing just the cameras.
    """
    exporter = find_executable(meshroom_root, "aliceVision_exportColoredPointCloud")
    dest.parent.mkdir(parents=True, exist_ok=True)
    code = run_streaming(
        [str(exporter), "-i", str(source), "-o", str(dest)],
        logfile, env=build_env(meshroom_root),
    )
    if code != 0 or not dest.is_file():
        return -1
    strip_camera_markers(dest, n_views)
    return ply_vertex_count(dest)


def process(name: str, preset_name: str, force: bool, keep_cache: bool,
            meshroom_root: Path) -> bool:
    src = INPUT_DIR / name
    out = OUTPUT_DIR / name
    cache = WORK_DIR / name
    preset = PRESETS[preset_name]

    images = list_images(src)
    if not images:
        log(f"[{name}] no images found in {src} - skipping")
        return False

    ply = out / f"{name}_dense.ply"
    if ply.is_file() and not force:
        log(f"[{name}] already done ({ply.name}) - use --force to redo")
        return True

    log("=" * 68)
    log(f"[{name}] {len(images)} images | preset '{preset.name}' ({preset.blurb})")
    log("=" * 68)

    out.mkdir(parents=True, exist_ok=True)
    logfile = out / "log.txt"
    if force and cache.exists():
        log(f"[{name}] clearing cache {cache}")
        shutil.rmtree(cache, ignore_errors=True)
    cache.mkdir(parents=True, exist_ok=True)

    # Deliberately no --cache: in 2025.1.0 passing it suppresses the project-file
    # setup and the run silently falls back to %TEMP%\MeshroomCache. Passing only
    # --save makes Meshroom put the cache next to the project file, which lands it
    # in work/<object>/MeshroomCache/ where we want it.
    cmd = [
        *meshroom_batch_cmd(meshroom_root),
        "--input", str(src),
        "--pipeline", "photogrammetry",
        "--toNode", TARGET_NODE,
        "--save", str(cache / f"{name}.mg"),
        "--paramOverrides", *preset.overrides(),
    ]

    started = time.time()
    code = run_streaming(cmd, logfile, env=build_env(meshroom_root))
    elapsed = time.time() - started

    if code != 0:
        log(f"[{name}] FAILED: meshroom_batch exited {code}. See {logfile}")
        return False

    cloud = find_dense_cloud(cache)
    if cloud is None:
        log(f"[{name}] FAILED: pipeline finished but no dense cloud found in {cache}")
        return False

    log(f"[{name}] exporting {cloud.name} -> {ply.name}")
    points = export_point_cloud(meshroom_root, cloud, ply, logfile, len(images))
    if points < 0:
        log(f"[{name}] FAILED: could not export {cloud} to PLY. See {logfile}")
        return False
    # A handful of points means the solve collapsed even though every node
    # reported success, which is worth failing loudly rather than shipping.
    if points < 1000:
        log(f"[{name}] FAILED: only {points} points - the reconstruction did not "
            f"converge. Check camera registration in {logfile}.")
        return False

    size_mb = ply.stat().st_size / (1024 * 1024)
    log(f"[{name}] done in {elapsed / 60:.1f} min -> {ply}")
    log(f"[{name}] {points:,} points ({size_mb:.1f} MB)")

    write_report(out / "report.txt", name, images, preset_name, elapsed, ply, cmd,
                 points)

    if not keep_cache:
        log(f"[{name}] removing cache {cache} (use --keep-cache to retain it)")
        shutil.rmtree(cache, ignore_errors=True)
    return True


def write_report(path: Path, name: str, images: list[Path], preset: str,
                 elapsed: float, ply: Path, cmd: list[str], points: int) -> None:
    path.write_text(
        "\n".join([
            f"object    : {name}",
            f"finished  : {dt.datetime.now().isoformat(timespec='seconds')}",
            f"images    : {len(images)}",
            f"preset    : {preset}",
            f"duration  : {elapsed / 60:.1f} min",
            f"points    : {points:,}",
            f"output    : {ply.name} ({ply.stat().st_size / (1024 * 1024):.1f} MB)",
            "",
            "command:",
            "  " + " ".join(cmd),
            "",
        ]),
        encoding="utf-8",
    )


def doctor() -> int:
    log(f"project    : {INPUT_DIR.parent}")
    log(f"gpu        : {gpu_summary()}")
    try:
        root = find_meshroom_root()
    except RigError as exc:
        log(f"meshroom   : NOT FOUND\n{exc}")
        return 1
    log(f"meshroom   : {root}")
    ok = True
    for stem in ("meshroom_batch", "aliceVision_cameraInit",
                 "aliceVision_depthMapEstimation",
                 "aliceVision_exportColoredPointCloud"):
        try:
            log(f"  {stem:32} {find_executable(root, stem)}")
        except RigError:
            log(f"  {stem:32} MISSING")
            ok = False

    objects = list_objects()
    if objects:
        log(f"objects    : {len(objects)} ({', '.join(objects)})")
    else:
        log(f"objects    : none - drop image folders into {INPUT_DIR}")
    free_gb = shutil.disk_usage(INPUT_DIR.parent).free / (1024 ** 3)
    log(f"disk free  : {free_gb:.1f} GB")
    if free_gb < 30:
        log("  WARNING: dense reconstruction needs plenty of scratch space.")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Headless AliceVision/Meshroom dense point cloud generation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="presets:\n" + "\n".join(
            f"  {n:<8} {p.blurb}" for n, p in PRESETS.items()
        ),
    )
    parser.add_argument("objects", nargs="*",
                        help="folder names under input/ (default: all pending)")
    parser.add_argument("-q", "--quality", choices=list(PRESETS),
                        default=DEFAULT_PRESET, help=f"default: {DEFAULT_PRESET}")
    parser.add_argument("-f", "--force", action="store_true",
                        help="recompute even if output already exists")
    parser.add_argument("--keep-cache", action="store_true",
                        help="keep work/<object>/ after a successful run")
    parser.add_argument("--list", action="store_true", help="list objects and exit")
    parser.add_argument("--doctor", action="store_true",
                        help="check the install and exit")
    args = parser.parse_args()

    if args.doctor:
        return doctor()

    available = list_objects()
    if args.list:
        if not available:
            log(f"No objects yet. Create a folder of images at {INPUT_DIR}\\<name>\\")
            return 0
        for name in available:
            done = (OUTPUT_DIR / name / f"{name}_dense.ply").is_file()
            log(f"  {'[done]' if done else '[    ]'} {name:<28} "
                f"{len(list_images(INPUT_DIR / name))} images")
        return 0

    targets = args.objects or available
    if not targets:
        log(f"Nothing to do. Drop a folder of images into {INPUT_DIR}\\<name>\\")
        return 0

    unknown = [t for t in targets if not (INPUT_DIR / t).is_dir()]
    if unknown:
        log(f"No such folder(s) under input/: {', '.join(unknown)}")
        return 1

    meshroom_root = find_meshroom_root()
    log(f"meshroom: {meshroom_root}")
    log(f"gpu     : {gpu_summary()}")

    failures = [
        name for name in targets
        if not process(name, args.quality, args.force, args.keep_cache, meshroom_root)
    ]

    log()
    log(f"{len(targets) - len(failures)}/{len(targets)} succeeded")
    if failures:
        log(f"failed: {', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RigError as exc:
        log(f"\nERROR: {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        log("\ninterrupted")
        sys.exit(130)
