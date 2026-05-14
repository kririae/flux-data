# Boundary Robustness Repro

Minimal scenes for classic low-tessellation boundary artifacts.  The mesh is a
unit sphere with only 63 vertices / 80 triangles and authored vertex normals.

Use the paired scenes to separate shading-normal issues from plain geometric
faceting:

```bash
./build/flux/flux-bin flux/data/boundary_robustness/low_div_sphere_smooth.toml
./build/flux/flux-bin flux/data/boundary_robustness/low_div_sphere_smooth_closeup.toml
./build/flux/flux-bin flux/data/boundary_robustness/low_div_sphere_face_normals.toml
```

- `low_div_sphere_smooth.toml` uses the authored vertex normals from the PLY.
- `low_div_sphere_smooth_closeup.toml` frames the silhouette artifact directly.
- `low_div_sphere_face_normals.toml` ignores authored normals and shades with
  geometric face normals.

If only the smooth-normal case shows the boundary artifact, the repro is in the
shading-normal / geometric-normal mismatch family.  If both scenes show the same
artifact, the first suspect is geometric resolution or ray/visibility behavior.
