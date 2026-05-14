# Hydra Instancing Test Scenes

Small USD scenes for FLux Hydra instancing regressions.

`material_spheres.usda` uses USD native instancing: every colored sphere is an
instance of the same prototype mesh, while the material binding is authored on
the instance root. USD imaging is expected to split those native instances into
material-compatible Hydra prototype groups before FLux consumes them.

`reference/material_spheres.exr` is a FLux self-regression reference for the
Hydra path. It is not an external renderer ground truth.
