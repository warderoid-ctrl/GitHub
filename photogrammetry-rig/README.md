# photogrammetry-rig

Headless AliceVision / Meshroom photogrammetry. Drop a folder of photos into
`input/`, run one command, get a dense `.ply` point cloud in `output/`.
No GUI involved at any point.

## Layout

```
photogrammetry-rig/
├─ input/<object>/        <- your photos, one folder per object
├─ output/<object>/       <- <object>_dense.ply, report.txt, log.txt
├─ work/<object>/         <- intermediate cache (large, deleted on success)
├─ tools/Meshroom-2025.1.0/   <- the binaries (installed by setup.ps1)
└─ scripts/
    ├─ setup.ps1          <- one-time install
    ├─ scan.py            <- the driver
    └─ rig.py             <- paths, presets, install discovery
```

`tools/` and `work/` are gitignored, as are the contents of `input/` and
`output/` — the repo tracks the scaffolding, not your gigabytes.

## One-time setup

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

Downloads Meshroom 2025.1.0 (~9.5 GiB), checks its MD5, extracts to `tools/`,
and verifies the install. The download resumes, so re-run it if your connection
drops. Then confirm everything is wired up:

```powershell
python scripts\scan.py --doctor
```

## Running a scan

```powershell
python scripts\scan.py                  # every object in input/ without output yet
python scripts\scan.py ceramic_mug      # one object
python scripts\scan.py ceramic_mug -q high
python scripts\scan.py ceramic_mug --force        # recompute from scratch
python scripts\scan.py --list           # what's queued, what's done
```

In VS Code, **Ctrl+Shift+B** runs all pending objects. `Terminal → Run Task…`
has the rest: pick a single object, force a redo, doctor, setup, clean cache.

## Quality presets

| Preset   | Features | Depth scale | SGM scale | Max points | Use for |
|----------|----------|-------------|-----------|------------|---------|
| `draft`  | normal   | 1/4         | 1/2       | 3 M        | Checking coverage before committing hours |
| `normal` | high     | 1/2         | 1/2       | 5 M        | Default — good detail, sane runtime |
| `high`   | high+    | 1/2         | 1/1       | 10 M       | Denser features and finer depth matching |
| `ultra`  | ultra    | 1/1         | 1/1       | 20 M       | Maximum detail; heavy on VRAM |

The two scale factors **multiply**: `draft` matches at 1/4 × 1/2 = 1/8 resolution.

`ultra` runs depth-map estimation at full resolution. On an 8 GB card that can
run out of memory with high-megapixel photos — if it does, fall back to `high`
or downsize the images.

On the bundled 6-image sample, `draft` yields ~65 K points and `normal` ~237 K,
which is a useful sanity check that the presets are taking effect.

## What it actually runs

`meshroom_batch --pipeline photogrammetry --toNode Meshing_1`, then
`aliceVision_exportColoredPointCloud` to turn AliceVision's `.abc` dense cloud
into a `.ply` that CloudCompare, MeshLab, and Blender all open directly.

The pipeline stops at `Meshing` because that node is what fuses the filtered
depth maps into the dense cloud. Mesh filtering and texturing are skipped — they
cost roughly as much again and produce a surface, not points. To add them, drop
the `--toNode` argument in [scripts/scan.py](scripts/scan.py) and collect the
`Texturing` output folder.

### Quirks of Meshroom 2025.1.0 this works around

Worth knowing before you edit [scripts/scan.py](scripts/scan.py), since each of
these fails in a way that looks like something else:

- **`--cache` is not used.** Passing it suppresses the project-file cache setup
  and the run silently writes to `%TEMP%\MeshroomCache` instead. Passing only
  `--save` puts the cache beside the project file, which is what we want.
- **`--paramOverrides` uses `NodeType:param=value`.** The dotted
  `NodeInstance.param` form does a prefix match, and `DepthMap.` is ambiguous
  between `DepthMap_1` and `DepthMapFilter_1`, which aborts the run.
- **Grouped parameters need their group.** `downscale` is top-level on the
  DepthMap node but `sgmScale` lives in its `sgm` group, so it is
  `sgm.sgmScale`.
- **`convertSfMFormat` is the wrong exporter.** It reads a dense cloud's
  landmarks as empty and writes a header-only PLY containing just the camera
  positions — succeeding with exit code 0 while producing nothing.
- **Camera markers are stripped.** `exportColoredPointCloud` prepends one pure
  green vertex per camera and has no flag to omit them, so `scan.py` removes
  them, but only when every candidate really is pure green.

A sample object, `sample_monstree`, ships in `input/` so you can verify the
install end to end before shooting anything:

```powershell
python scripts\scan.py sample_monstree -q draft
```

It should finish in a couple of minutes and report roughly 65,000 points. Delete
the folder once you trust the setup.

## Expected runtimes

Rough, for ~80 photos at 24 MP on an RTX 4070 Laptop:

| Preset  | Time |
|---------|------|
| draft   | 10–15 min |
| normal  | 30–50 min |
| high    | 45–75 min |
| ultra   | 2 h+ |

Feature extraction and depth-map estimation dominate. The cache in `work/` can
reach 20–40 GB mid-run before it's cleaned up, so keep headroom on `C:`.

## When a scan comes out badly

Check `output/<object>/log.txt` — the SfM stage reports how many cameras it
registered. If that number is well under your photo count, the problem is the
photos, not the settings: see the shooting notes in
[input/README.md](input/README.md). Re-running at a higher preset will not
rescue a set that didn't match.

Pass `--keep-cache` to retain `work/<object>/` for inspection, and open
`work/<object>/<object>.mg` in the Meshroom GUI to see exactly where the graph
stalled.
