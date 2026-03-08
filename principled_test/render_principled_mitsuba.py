#!/usr/bin/env python3
"""Render Mitsuba references for the principled test scene pack."""

from __future__ import annotations

import argparse
import os
import tomllib
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent

SCENE_METADATA = {
    "principled_reference": {
        "filename": "principled_reference.toml",
        "description": "Broad six-object Principled reference scene",
    },
    "principled_inside_camera": {
        "filename": "principled_inside_camera.toml",
        "description": "Camera starts inside a transmissive sphere",
    },
    "principled_eta_one_warning": {
        "filename": "principled_eta_one_warning.toml",
        "description": "Transmissive sphere with eta = 1.0",
    },
    "principled_eta_less_than_one": {
        "filename": "principled_eta_less_than_one.toml",
        "description": "Transmissive sphere with eta < 1.0",
    },
    "principled_total_internal_reflection": {
        "filename": "principled_total_internal_reflection.toml",
        "description": "Inside-the-medium total internal reflection setup",
    },
    "principled_metallic_zero_specular": {
        "filename": "principled_metallic_zero_specular.toml",
        "description": "Metallic sphere with specular = 0.0",
    },
}

PRINCIPLED_COLOR_FIELDS = {"base_color"}
PRINCIPLED_SCALAR_FIELDS = {
    "anisotropic",
    "clearcoat",
    "clearcoat_gloss",
    "eta",
    "flatness",
    "metallic",
    "roughness",
    "sheen",
    "sheen_tint",
    "spec_tint",
    "spec_trans",
    "specular",
}


def rgb(values):
    return {"type": "rgb", "value": [float(component) for component in values]}


def normalize_scene_key(scene_name: str) -> str:
    candidate = Path(scene_name).name
    if candidate.endswith(".toml"):
        candidate = candidate[:-5]
    return candidate


def canonical_scene_path(scene_key: str) -> Path:
    return THIS_DIR / SCENE_METADATA[scene_key]["filename"]


def resolve_scene_path(scene_name: str) -> tuple[str, Path]:
    scene_key = normalize_scene_key(scene_name)
    if scene_key not in SCENE_METADATA:
        available = ", ".join(sorted(SCENE_METADATA))
        raise KeyError(f"Unknown scene '{scene_name}'. Available scenes: {available}")

    candidate = Path(scene_name)
    if candidate.suffix == ".toml" and candidate.exists():
        return scene_key, candidate.resolve()

    return scene_key, canonical_scene_path(scene_key)


def load_flux_scene_toml(scene_name: str) -> tuple[str, Path, dict]:
    scene_key, scene_path = resolve_scene_path(scene_name)
    with scene_path.open("rb") as handle:
        return scene_key, scene_path, tomllib.load(handle)


def unwrap_constant(value):
    if not isinstance(value, dict):
        return value
    if value.get("type") != "constant":
        return value
    if "color" in value:
        return value["color"]
    if "value" in value:
        return value["value"]
    raise ValueError(f"Unsupported constant texture payload: {value!r}")


def convert_scalar(value, field_name: str) -> float:
    value = unwrap_constant(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (list, tuple)) and len(value) == 1:
        return float(value[0])
    raise ValueError(f"Unsupported scalar value for '{field_name}': {value!r}")


def convert_color(value, field_name: str) -> dict:
    value = unwrap_constant(value)
    if isinstance(value, (int, float)):
        scalar = float(value)
        return rgb([scalar, scalar, scalar])
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return rgb(value)
    if isinstance(value, (list, tuple)) and len(value) == 1:
        scalar = float(value[0])
        return rgb([scalar, scalar, scalar])
    raise ValueError(f"Unsupported color value for '{field_name}': {value!r}")


def convert_diffuse_bsdf(bsdf: dict) -> dict:
    reflectance = bsdf.get("R", bsdf.get("reflectance", 0.5))
    return {
        "type": "diffuse",
        "reflectance": convert_color(reflectance, "diffuse.reflectance"),
    }


def convert_principled_bsdf(bsdf: dict) -> dict:
    result = {"type": "principled"}
    for key, value in bsdf.items():
        if key in {"name", "type"}:
            continue
        if key in PRINCIPLED_COLOR_FIELDS:
            result[key] = convert_color(value, f"principled.{key}")
            continue
        if key in PRINCIPLED_SCALAR_FIELDS:
            result[key] = convert_scalar(value, f"principled.{key}")
            continue
        raise ValueError(f"Unsupported principled property '{key}'")
    return result


def convert_bsdf(bsdf: dict) -> dict:
    bsdf_type = bsdf["type"]
    if bsdf_type == "diffuse":
        return convert_diffuse_bsdf(bsdf)
    if bsdf_type == "principled":
        return convert_principled_bsdf(bsdf)
    raise ValueError(f"Unsupported BSDF type '{bsdf_type}'")


def resolve_bsdf(primitive: dict, named_bsdfs: dict[str, dict]) -> dict:
    bsdf_ref = primitive["bsdf"]
    if isinstance(bsdf_ref, str):
        if bsdf_ref not in named_bsdfs:
            raise KeyError(f"Primitive references unknown BSDF '{bsdf_ref}'")
        return convert_bsdf(named_bsdfs[bsdf_ref])
    if isinstance(bsdf_ref, dict):
        return convert_bsdf(bsdf_ref)
    raise ValueError(f"Unsupported primitive BSDF reference: {bsdf_ref!r}")


def convert_emitter(light: dict) -> dict:
    if light.get("type") != "area":
        raise ValueError(f"Unsupported light type '{light.get('type')}'")
    return {
        "type": "area",
        "radiance": convert_color(light["emission"], "light.emission"),
    }


def convert_envmap(envmap: dict) -> dict:
    texture = envmap.get("texture")
    if not isinstance(texture, dict) or texture.get("type") != "constant":
        raise ValueError("Only constant envmaps are supported for principled test scenes")

    radiance = convert_color(texture.get("color", texture.get("value")), "envmap.texture")
    scale = float(envmap.get("scale", 1.0))
    if scale != 1.0:
        radiance = rgb([scale * component for component in radiance["value"]])

    return {
        "type": "constant",
        "radiance": radiance,
    }


def build_sensor(mi, camera: dict, width: int, height: int, spp: int) -> dict:
    return {
        "type": "perspective",
        "fov": float(camera["fov"]),
        "fov_axis": "y",
        "to_world": mi.ScalarTransform4f.look_at(
            origin=[float(component) for component in camera["position"]],
            target=[float(component) for component in camera["look_at"]],
            up=[float(component) for component in camera.get("ref_up", [0.0, 1.0, 0.0])],
        ),
        "film": {
            "type": "hdrfilm",
            "width": int(width),
            "height": int(height),
            "pixel_format": "rgb",
            "component_format": "float32",
            "rfilter": {"type": "box"},
        },
        "sampler": {
            "type": "independent",
            "sample_count": int(spp),
        },
    }


def build_integrator(integrator: dict) -> dict:
    if integrator.get("type") != "path":
        raise ValueError(
            f"Only path integrators are supported, got '{integrator.get('type')}'"
        )

    result = {"type": "path"}
    for key in ("max_depth", "rr_depth"):
        if key in integrator:
            result[key] = int(integrator[key])
    return result


def build_mitsuba_scene_dict_from_toml(
    mi,
    flux_scene: dict,
    *,
    width: int | None = None,
    height: int | None = None,
    spp: int | None = None,
) -> dict:
    camera = flux_scene["camera"]
    film = flux_scene["film"]
    integrator = flux_scene["integrator"]
    envmap = flux_scene["envmap"]

    resolution = film["resolution"]
    width = int(width if width is not None else resolution[0])
    height = int(height if height is not None else resolution[1])
    spp = int(spp if spp is not None else film["num_samples"])

    scene = {
        "type": "scene",
        "integrator": build_integrator(integrator),
        "sensor": build_sensor(mi, camera, width, height, spp),
        "envmap": convert_envmap(envmap),
    }

    named_bsdfs = {entry["name"]: entry for entry in flux_scene.get("bsdf", [])}

    for index, primitive in enumerate(flux_scene.get("primitive", [])):
        if primitive.get("type") != "sphere":
            raise ValueError(
                f"Only sphere primitives are supported, got '{primitive.get('type')}'"
            )

        scene_object = {
            "type": "sphere",
            "center": [float(component) for component in primitive["center"]],
            "radius": float(primitive["radius"]),
            "bsdf": resolve_bsdf(primitive, named_bsdfs),
        }
        if "light" in primitive:
            scene_object["emitter"] = convert_emitter(primitive["light"])

        scene[f"primitive_{index}"] = scene_object

    return scene


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render Mitsuba references for the principled Flux scene pack."
    )
    parser.add_argument(
        "--scene",
        help="Scene basename or TOML filename/path, e.g. principled_reference or principled_reference.toml.",
    )
    parser.add_argument(
        "--output",
        help="Output EXR path. Defaults to /tmp/<scene>_mitsuba.exr.",
    )
    parser.add_argument(
        "--spp",
        type=int,
        help="Override the scene-default sample count.",
    )
    parser.add_argument(
        "--res",
        type=int,
        nargs=2,
        metavar=("WIDTH", "HEIGHT"),
        help="Override the scene-default resolution.",
    )
    parser.add_argument(
        "--variant",
        default=os.environ.get("MITSUBA_VARIANT", "scalar_rgb"),
        help="Mitsuba variant to use (default: MITSUBA_VARIANT or scalar_rgb).",
    )
    parser.add_argument(
        "--list-scenes",
        action="store_true",
        help="Print supported scene keys and exit.",
    )
    args = parser.parse_args()
    if not args.list_scenes and not args.scene:
        parser.error("--scene is required unless --list-scenes is used")
    return args


def list_scenes():
    for scene_key, metadata in SCENE_METADATA.items():
        print(f"{scene_key}: {metadata['description']}")


def main():
    args = parse_args()
    if args.list_scenes:
        list_scenes()
        return 0

    scene_key, scene_path, flux_scene = load_flux_scene_toml(args.scene)
    width = args.res[0] if args.res else None
    height = args.res[1] if args.res else None
    spp = args.spp
    output = args.output or f"/tmp/{scene_key}_mitsuba.exr"

    import mitsuba as mi

    mi.set_variant(args.variant)
    scene_dict = build_mitsuba_scene_dict_from_toml(
        mi,
        flux_scene,
        width=width,
        height=height,
        spp=spp,
    )
    scene = mi.load_dict(scene_dict)

    final_width = scene_dict["sensor"]["film"]["width"]
    final_height = scene_dict["sensor"]["film"]["height"]
    final_spp = scene_dict["sensor"]["sampler"]["sample_count"]
    print(
        f"Rendering {scene_key} from {scene_path} at "
        f"{final_width}x{final_height} with {final_spp} spp "
        f"using Mitsuba variant '{args.variant}'..."
    )
    image = mi.render(scene)
    mi.util.write_bitmap(output, image)
    print(f"Saved {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
