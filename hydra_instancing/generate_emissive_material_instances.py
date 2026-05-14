#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade


def create_mtlx_standard_surface(
    stage: Usd.Stage,
    path: str,
    base_color: Gf.Vec3f,
    emission_color: Gf.Vec3f,
    emission: float,
) -> UsdShade.Material:
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/MtlxSurface")
    shader.CreateIdAttr("ND_standard_surface_surfaceshader")
    shader.CreateInput("base", Sdf.ValueTypeNames.Float).Set(1.0)
    shader.CreateInput("base_color", Sdf.ValueTypeNames.Color3f).Set(base_color)
    shader.CreateInput("emission", Sdf.ValueTypeNames.Float).Set(emission)
    shader.CreateInput("emission_color", Sdf.ValueTypeNames.Color3f).Set(
        emission_color
    )
    shader.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(0.0)
    shader.CreateInput("specular_roughness", Sdf.ValueTypeNames.Float).Set(0.55)
    shader.CreateOutput("out", Sdf.ValueTypeNames.Token)
    material.CreateOutput("mtlx:surface", Sdf.ValueTypeNames.Token).ConnectToSource(
        shader.ConnectableAPI(), "out"
    )
    return material


def create_preview_material(stage: Usd.Stage, path: str, color: Gf.Vec3f) -> UsdShade.Material:
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(color)
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.62)
    shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def define_panel_prototype(stage: Usd.Stage) -> None:
    proto = UsdGeom.Xform.Define(stage, "/_Prototype/Panel")
    proto.GetPrim().SetSpecifier(Sdf.SpecifierClass)

    mesh = UsdGeom.Mesh.Define(stage, "/_Prototype/Panel/mesh")
    mesh.CreatePointsAttr(
        [
            Gf.Vec3f(-0.45, -0.45, 0.0),
            Gf.Vec3f(0.45, -0.45, 0.0),
            Gf.Vec3f(0.45, 0.45, 0.0),
            Gf.Vec3f(-0.45, 0.45, 0.0),
        ]
    )
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    mesh.CreateNormalsAttr([Gf.Vec3f(0.0, 0.0, 1.0)] * 4)
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)


def add_ground(stage: Usd.Stage, material: UsdShade.Material) -> None:
    mesh = UsdGeom.Mesh.Define(stage, "/World/ground")
    mesh.CreatePointsAttr(
        [
            Gf.Vec3f(-3.6, -0.6, -1.2),
            Gf.Vec3f(3.6, -0.6, -1.2),
            Gf.Vec3f(3.6, -0.6, 1.5),
            Gf.Vec3f(-3.6, -0.6, 1.5),
        ]
    )
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)


def add_panel_instances(stage: Usd.Stage, materials: list[UsdShade.Material]) -> None:
    UsdGeom.Scope.Define(stage, "/World/instances")
    positions = [
        Gf.Vec3d(-1.65, 0.15, 0.0),
        Gf.Vec3d(-0.55, 0.15, 0.0),
        Gf.Vec3d(0.55, 0.15, 0.0),
        Gf.Vec3d(1.65, 0.15, 0.0),
    ]
    for index, position in enumerate(positions):
        xform = UsdGeom.Xform.Define(stage, f"/World/instances/panel_{index:02d}")
        prim = xform.GetPrim()
        prim.GetReferences().AddInternalReference("/_Prototype/Panel")
        prim.SetInstanceable(True)
        xform.AddTranslateOp().Set(position)
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(materials[index % len(materials)])


def add_camera(stage: Usd.Stage) -> None:
    camera = UsdGeom.Camera.Define(stage, "/World/camera")
    camera.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.45, 4.8))
    camera.AddRotateXYZOp().Set(Gf.Vec3f(-2.0, 0.0, 0.0))
    camera.CreateFocalLengthAttr(38.0)
    camera.CreateVerticalApertureAttr(20.955)


def main() -> None:
    output = Path(__file__).with_name("emissive_material_instances.usda")
    stage = Usd.Stage.CreateNew(str(output))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.SetDefaultPrim(UsdGeom.Xform.Define(stage, "/World").GetPrim())

    define_panel_prototype(stage)
    warm = create_mtlx_standard_surface(
        stage,
        "/World/materials/warm_emissive",
        Gf.Vec3f(0.12, 0.08, 0.05),
        Gf.Vec3f(1.0, 0.42, 0.16),
        4.0,
    )
    cool = create_mtlx_standard_surface(
        stage,
        "/World/materials/cool_emissive",
        Gf.Vec3f(0.04, 0.07, 0.12),
        Gf.Vec3f(0.20, 0.65, 1.0),
        3.0,
    )
    ground = create_preview_material(
        stage, "/World/materials/matte_grey", Gf.Vec3f(0.35, 0.36, 0.38)
    )

    add_ground(stage, ground)
    add_panel_instances(stage, [warm, cool])
    add_camera(stage)

    stage.GetRootLayer().Save()


if __name__ == "__main__":
    main()
