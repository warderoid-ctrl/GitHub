"""Shared helpers: locating the Meshroom install, the project layout, and presets."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
WORK_DIR = ROOT / "work"
TOOLS_DIR = ROOT / "tools"

IMAGE_SUFFIXES = {
    ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".exr",
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".orf", ".rw2",
}


@dataclass(frozen=True)
class Preset:
    """A quality preset, expressed as meshroom_batch --paramOverrides values.

    ``downscale`` is the DepthMap downscale factor: 1 is full resolution and the
    most VRAM-hungry, 4 is quarter resolution and quick. On an 8 GB card, 1 will
    only survive modest image resolutions, which is why it is confined to
    ``ultra``.

    ``sgm_scale`` is applied *on top of* ``downscale``, so the two multiply --
    downscale=4 with sgm_scale=4 means matching at 1/16 resolution, which is far
    coarser than it looks.
    """

    name: str
    describer_preset: str
    describer_quality: str
    downscale: int
    sgm_scale: int
    max_points: int
    blurb: str

    def overrides(self) -> list[str]:
        # The NODETYPE:param form targets nodes by type. The NODEINSTANCE.param
        # form does a prefix match, where "DepthMap." is ambiguous between
        # DepthMap_1 and DepthMapFilter_1 and aborts the run.
        return [
            f"FeatureExtraction:describerPreset={self.describer_preset}",
            f"FeatureExtraction:describerQuality={self.describer_quality}",
            f"DepthMap:downscale={self.downscale}",
            # sgmScale sits inside the node's "sgm" group, unlike downscale.
            f"DepthMap:sgm.sgmScale={self.sgm_scale}",
            f"Meshing:maxPoints={self.max_points}",
            # Keep the fused cloud rather than only the meshed surface.
            "Meshing:saveRawDensePointCloud=True",
        ]


PRESETS: dict[str, Preset] = {
    "draft": Preset("draft", "normal", "normal", 4, 2, 3_000_000,
                    "fastest, for checking coverage before a real run"),
    "normal": Preset("normal", "high", "normal", 2, 2, 5_000_000,
                     "sensible default"),
    "high": Preset("high", "high", "high", 2, 1, 10_000_000,
                   "denser features and finer depth matching"),
    "ultra": Preset("ultra", "ultra", "high", 1, 1, 20_000_000,
                    "full-resolution depth maps; VRAM-hungry"),
}
DEFAULT_PRESET = "normal"


class RigError(RuntimeError):
    """Something the user needs to fix, reported without a traceback."""


# --------------------------------------------------------------------------
# Locating the Meshroom install
# --------------------------------------------------------------------------

def find_meshroom_root() -> Path:
    """Return the Meshroom install directory.

    Honours ``MESHROOM_HOME`` so an install living outside the repo can be used,
    otherwise picks the newest ``tools/Meshroom-*`` directory.
    """
    env = os.environ.get("MESHROOM_HOME")
    if env:
        root = Path(env)
        if not root.is_dir():
            raise RigError(f"MESHROOM_HOME points at {root}, which is not a directory.")
        return root

    candidates = sorted(
        (p for p in TOOLS_DIR.glob("Meshroom-*") if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )
    if not candidates:
        raise RigError(
            "No Meshroom install found.\n"
            "  Run:  powershell -ExecutionPolicy Bypass -File scripts\\setup.ps1\n"
            "  Or set MESHROOM_HOME to an existing install."
        )
    return candidates[0]


def find_executable(root: Path, stem: str) -> Path:
    """Find ``stem``(.exe) anywhere under a Meshroom install.

    The layout has shifted between releases, so search rather than hardcode.
    """
    names = [f"{stem}.exe", stem]
    for directory in (root, root / "bin", root / "aliceVision" / "bin"):
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    for name in names:
        for candidate in root.rglob(name):
            if candidate.is_file():
                return candidate
    raise RigError(f"Could not find '{stem}' under {root}.")


def meshroom_batch_cmd(root: Path) -> list[str]:
    """Return the command prefix that runs meshroom_batch.

    Prefers the bundled executable; falls back to the Python entry point that
    older bundles ship instead.
    """
    try:
        return [str(find_executable(root, "meshroom_batch"))]
    except RigError:
        pass

    script = next(
        (p for p in (root / "meshroom_batch", root / "bin" / "meshroom_batch",
                     root / "meshroom_batch.py") if p.is_file()),
        None,
    )
    if script is None:
        raise RigError(
            f"Found a Meshroom install at {root} but no meshroom_batch entry point.\n"
            "The archive may have extracted incompletely."
        )
    python = shutil.which("python") or sys.executable
    return [python, str(script)]


# --------------------------------------------------------------------------
# Project layout
# --------------------------------------------------------------------------

def build_env(root: Path) -> dict[str, str]:
    """Environment for the AliceVision binaries.

    meshroom_batch sets ALICEVISION_ROOT for itself, but the aliceVision_* tools
    invoked directly need it too or they cannot find the bundled OCIO colour
    config and sensor database.
    """
    env = dict(os.environ)
    env.setdefault("ALICEVISION_ROOT", str(root / "aliceVision"))
    env.setdefault(
        "ALICEVISION_SENSOR_DB",
        str(root / "aliceVision" / "share" / "aliceVision" / "cameraSensors.db"),
    )
    return env


def list_images(folder: Path) -> list[Path]:
    return sorted(
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )


def list_objects() -> list[str]:
    """Every subfolder of input/ that holds at least one image."""
    if not INPUT_DIR.is_dir():
        return []
    return sorted(
        p.name for p in INPUT_DIR.iterdir()
        if p.is_dir() and not p.name.startswith((".", "_")) and list_images(p)
    )


def gpu_summary() -> str:
    """One-line GPU description, or a warning if nvidia-smi is unavailable."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return "nvidia-smi not found - CUDA depth maps will probably fail"
    try:
        out = subprocess.run(
            [smi, "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=20, check=True,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError) as exc:
        return f"nvidia-smi failed: {exc}"
    return out.splitlines()[0].strip() if out else "no NVIDIA GPU reported"
