# Drop your images here

One folder per object. The folder name becomes the output name.

```
input/
├─ ceramic_mug/          ->  output/ceramic_mug/ceramic_mug_dense.ply
│   ├─ IMG_0001.jpg
│   ├─ IMG_0002.jpg
│   └─ ...
└─ bronze_figurine/      ->  output/bronze_figurine/bronze_figurine_dense.ply
    └─ ...
```

Subfolders inside an object are searched too, so a camera's `DCIM/100CANON`
layout works as-is.

## Shooting for a good point cloud

- **40–150 photos** per object. Below ~25 the solve gets unreliable.
- **60–80% overlap** between neighbouring shots; orbit in rings at 2–3 heights.
- **Locked focus and exposure**, and the highest f-number you can light for —
  out-of-focus edges are the most common cause of a sparse result.
- **Diffuse, even light.** Hard shadows move with the object and confuse matching.
- **Matte surfaces only.** Shiny, transparent, or plain untextured objects
  (a white mug, glass, chrome) will not reconstruct — dull them with chalk spray
  or dust if you can.
- **Do not crop or rotate** afterwards; that strips the EXIF focal length the
  solver relies on.
