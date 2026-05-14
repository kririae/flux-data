#!/usr/bin/env python3

from __future__ import annotations

import math
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade


def create_preview_material(stage: Usd.Stage, path: str, color: Gf.Vec3f) -> UsdShade.Material:
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(color)
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.46)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def sphere_mesh(radius: float = 0.5, rings: int = 10, segments: int = 20):
    points: list[Gf.Vec3f] = []
    normals: list[Gf.Vec3f] = []

    for ring in range(rings + 1):
        theta = math.pi * ring / rings
        sin_t = math.sin(theta)
        cos_t = math.cos(theta)
        for segment in range(segments):
            phi = 2.0 * math.pi * segment / segments
            n = Gf.Vec3f(
                float(sin_t * math.cos(phi)),
                float(cos_t),
                float(sin_t * math.sin(phi)),
            )
            points.append(n * radius)
            normals.append(n)

    counts: list[int] = []
    indices: list[int] = []
    for ring in range(rings):
        for segment in range(segments):
            a = ring * segments + segment
            b = ring * segments + (segment + 1) % segments
            c = (ring + 1) * segments + (segment + 1) % segments
            d = (ring + 1) * segments + segment
            counts.append(4)
            indices.extend([a, b, c, d])

    return points, normals, counts, indices


def define_sphere_prototype(stage: Usd.Stage) -> None:
    proto = UsdGeom.Xform.Define(stage, "/_Prototype/Sphere")
    proto.GetPrim().SetSpecifier(Sdf.SpecifierClass)

    points, normals, counts, indices = sphere_mesh()
    mesh = UsdGeom.Mesh.Define(stage, "/_Prototype/Sphere/mesh")
    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexCountsAttr(counts)
    mesh.CreateFaceVertexIndicesAttr(indices)
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    mesh.CreateNormalsAttr(normals)
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)


def add_ground(stage: Usd.Stage, material: UsdShade.Material) -> None:
    mesh = UsdGeom.Mesh.Define(stage, "/World/ground")
    mesh.CreatePointsAttr(
        [
            Gf.Vec3f(-5.5, -0.52, -3.8),
            Gf.Vec3f(5.5, -0.52, -3.8),
            Gf.Vec3f(5.5, -0.52, 3.8),
            Gf.Vec3f(-5.5, -0.52, 3.8),
        ]
    )
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)


def add_instances(stage: Usd.Stage, materials: list[UsdShade.Material]) -> None:
    root = UsdGeom.Scope.Define(stage, "/World/instances")
    del root

    rows = 4
    cols = 7
    spacing = 1.25
    for row in range(rows):
        for col in range(cols):
            index = row * cols + col
            xform = UsdGeom.Xform.Define(stage, f"/World/instances/sphere_{index:02d}")
            prim = xform.GetPrim()
            prim.GetReferences().AddInternalReference("/_Prototype/Sphere")
            prim.SetInstanceable(True)

            x = (col - (cols - 1) * 0.5) * spacing
            z = (row - (rows - 1) * 0.5) * spacing
            xform.AddTranslateOp().Set(Gf.Vec3d(x, 0.0, z))
            UsdShade.MaterialBindingAPI.Apply(prim).Bind(materials[index % len(materials)])


def add_camera_and_lights(stage: Usd.Stage) -> None:
    camera = UsdGeom.Camera.Define(stage, "/World/camera")
    camera.AddTranslateOp().Set(Gf.Vec3d(0.0, 3.2, 7.8))
    camera.AddRotateXYZOp().Set(Gf.Vec3f(-21.0, 0.0, 0.0))
    camera.CreateFocalLengthAttr(35.0)
    camera.CreateVerticalApertureAttr(20.955)

    dome = UsdLux.DomeLight.Define(stage, "/World/domeLight")
    dome.CreateIntensityAttr(0.35)
    dome.CreateColorAttr(Gf.Vec3f(0.72, 0.80, 1.0))

    key = UsdLux.RectLight.Define(stage, "/World/keyLight")
    key.CreateIntensityAttr(320.0)
    key.CreateWidthAttr(4.0)
    key.CreateHeightAttr(3.0)
    key.AddTranslateOp().Set(Gf.Vec3d(-2.2, 4.0, 3.5))
    key.AddRotateXYZOp().Set(Gf.Vec3f(-55.0, -18.0, 0.0))


def main() -> None:
    output = Path(__file__).with_name("material_spheres.usda")
    stage = Usd.Stage.CreateNew(str(output))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.SetDefaultPrim(UsdGeom.Xform.Define(stage, "/World").GetPrim())

    define_sphere_prototype(stage)

    red = create_preview_material(stage, "/World/materials/red", Gf.Vec3f(0.92, 0.12, 0.08))
    green = create_preview_material(stage, "/World/materials/green", Gf.Vec3f(0.12, 0.72, 0.24))
    blue = create_preview_material(stage, "/World/materials/blue", Gf.Vec3f(0.10, 0.28, 0.92))
    yellow = create_preview_material(stage, "/World/materials/yellow", Gf.Vec3f(0.95, 0.74, 0.12))
    violet = create_preview_material(stage, "/World/materials/violet", Gf.Vec3f(0.62, 0.22, 0.86))
    ground = create_preview_material(stage, "/World/materials/matte_grey", Gf.Vec3f(0.45, 0.47, 0.50))

    add_ground(stage, ground)
    add_instances(stage, [red, green, blue, yellow, violet])
    add_camera_and_lights(stage)

    stage.GetRootLayer().Save()


if __name__ == "__main__":
    main()
