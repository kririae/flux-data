# Principled Reference Scene Pack

This directory contains a small, stable scene pack for comparing Flux's
`principled` BSDF against Mitsuba's `principled` implementation.

## Scene Inventory

- `principled_reference.toml` — broad outside-camera reference with six
  objects covering diffuse, metallic, clearcoat, specular transmission,
  sheen/flatness, and a glossy white dielectric.
- `principled_inside_camera.toml` — camera starts inside a transmissive
  sphere and looks back out toward external markers.
- `principled_eta_one_warning.toml` — transmissive scene with `eta = 1.0`
  so Flux can exercise the host-side warning/adjustment path.
- `principled_eta_less_than_one.toml` — transmissive scene with `eta < 1.0`
  to cover the less-dense-side convention.
- `principled_total_internal_reflection.toml` — camera starts inside the
  sphere at an angle chosen to exceed the critical angle for `eta = 1.5`.
- `principled_metallic_zero_specular.toml` — metallic reference with
  `metallic = 1.0` and `specular = 0.0` so the metallic path remains visible.

The narrow transmissive scenes intentionally share a common layout:
one Principled sphere in front of colored marker spheres, with a warm
back light and a cool side light. That keeps image differences easy to
interpret while changing only the IOR/camera condition being tested.

`principled_eta_one_warning.toml` is primarily a host-side warning and
normalization-path check inside Flux. Keep it in the reference pack, but
do not treat it as the main pixel-oracle threshold gate for Principled
parity.

## Render With Flux

From the repository root:

```bash
build-cuda13/flux/flux-bin flux/data/principled_test/principled_reference.toml \
  -o /tmp/principled_reference_flux.exr
```

Swap in any of the six scene files above.

## Render With Mitsuba

Activate the Mitsuba environment you plan to use later, then run:

```bash
python flux/data/principled_test/render_principled_mitsuba.py \
  --scene principled_reference.toml \
  --output /tmp/principled_reference_mitsuba.exr
```

Useful options:

- `--scene` accepts either a supported basename such as
  `principled_reference` or a TOML filename/path such as
  `flux/data/principled_test/principled_reference.toml`.
- `--spp` overrides the scene-default sample count.
- `--res WIDTH HEIGHT` overrides the scene-default resolution.
- `--variant` selects the Mitsuba variant. If omitted, the script uses
  `MITSUBA_VARIANT` when available, otherwise `scalar_rgb`.
- `--list-scenes` prints all supported scene keys.

## Compare Flux vs Mitsuba EXRs

```bash
python flux/data/principled_test/compare_renders.py \
  /tmp/principled_reference_flux.exr \
  /tmp/principled_reference_mitsuba.exr \
  --comparison-output /tmp/principled_reference_compare.png \
  --rmse-threshold 0.02 \
  --max-threshold 0.10
```

`compare_renders.py` prints RMSE, MAE, and max absolute error. It exits
non-zero if any provided threshold is exceeded. When Pillow is installed,
`--comparison-output` writes a PNG laid out as:

`[Flux tonemapped | Mitsuba tonemapped | scaled absolute error]`
