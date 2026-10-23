"""Sculpts FinBoy's hard-surface 3D assets in Blender and exports raw glTF binaries.

Run through `pnpm --filter @finboy/web assets:3d` (scripts/3d/build-assets.mjs), which
compresses the output with gltfpack into public/models/. Direct use:

    Blender --background --factory-startup --python build_assets.py -- <out_dir>

Units: coin radius 1, dome radius 1. Front faces point +Z, and the exporter keeps
Blender's Z-up axes so the runtime can rely on that orientation.

Assets
- coin.glb: "Coin" (84-ridge reeded edge, ~40k tris) for close-ups and "CoinLite"
  (48 broad ridges, coarser relief) for small or many instances. Raised rim, gently
  dished field, the brand ₹ stroke path in beveled relief on the obverse and a striped
  mark on the reverse.
- check-dome.glb: "CheckDome", a filleted hemisphere with a rim bead and a rounded
  check-outline ridge on its slightly convex face.
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

# ----------------------------------------------------------------------------- helpers


def smoothstep(edge0, edge1, x):
    t = min(max((x - edge0) / (edge1 - edge0), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def metal_material(name):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Metallic"].default_value = 1.0
        bsdf.inputs["Roughness"].default_value = 0.2
    return material


def lathe(name, profile, segments, radius_fn=None):
    """Revolves (r, z) points around Z. r == 0 points become poles.

    radius_fn(theta, r, z) returns a sculpted radius per vertex (used for coin reeding).
    """
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r <= 1e-9:
            rings.append([bm.verts.new((0.0, 0.0, z))])
            continue
        ring = []
        for step in range(segments):
            theta = 2.0 * math.pi * step / segments
            radius = radius_fn(theta, r, z) if radius_fn else r
            ring.append(bm.verts.new((radius * math.cos(theta), radius * math.sin(theta), z)))
        rings.append(ring)

    for a, b in zip(rings, rings[1:]):
        for step in range(segments):
            nxt = (step + 1) % segments
            if len(a) == 1:
                bm.faces.new((a[0], b[step], b[nxt]))
            elif len(b) == 1:
                bm.faces.new((a[step], a[nxt], b[0]))
            else:
                bm.faces.new((a[step], a[nxt], b[nxt], b[step]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def segment_distance(px, py, ax, ay, bx, by):
    """Distance from grid points to segment AB (vectorised)."""
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-12:
        return np.hypot(px - ax, py - ay)
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / length_sq, 0.0, 1.0)
    return np.hypot(px - (ax + t * dx), py - (ay + t * dy))


def polyline_distance(px, py, points):
    distance = np.full(px.shape, np.inf)
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        distance = np.minimum(distance, segment_distance(px, py, ax, ay, bx, by))
    return distance


def cubic(p0, p1, p2, p3, steps=48):
    out = []
    for index in range(steps + 1):
        t = index / steps
        u = 1.0 - t
        out.append(
            (
                u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
            )
        )
    return out


def contour_loops(values, xs, ys, level):
    """Closed iso-lines (value == level, inside < level) of a sampled field.

    Marching squares on boundary cells only; saddles resolve with the cell centre.
    The field must be outside the level along the grid border.
    """
    inside = values < level
    case = (
        inside[:-1, :-1].astype(np.uint8)
        | (inside[:-1, 1:].astype(np.uint8) << 1)
        | (inside[1:, 1:].astype(np.uint8) << 2)
        | (inside[1:, :-1].astype(np.uint8) << 3)
    )
    # Cell edges: 0 bottom, 1 right, 2 top, 3 left.
    table = {
        1: [(3, 0)], 2: [(0, 1)], 3: [(3, 1)], 4: [(1, 2)], 6: [(0, 2)], 7: [(3, 2)],
        8: [(2, 3)], 9: [(0, 2)], 11: [(1, 2)], 12: [(1, 3)], 13: [(0, 1)], 14: [(3, 0)],
    }

    def edge_key(j, i, edge):
        if edge == 0:
            return ("h", j, i)
        if edge == 1:
            return ("v", j, i + 1)
        if edge == 2:
            return ("h", j + 1, i)
        return ("v", j, i)

    neighbours = {}

    def link(a, b):
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)

    for j, i in zip(*np.nonzero((case != 0) & (case != 15))):
        kind = int(case[j, i])
        if kind in (5, 10):
            centre_inside = values[j : j + 2, i : i + 2].mean() < level
            if (kind == 5) == centre_inside:
                pairs = [(0, 1), (2, 3)]
            else:
                pairs = [(3, 0), (1, 2)]
        else:
            pairs = table[kind]
        for a, b in pairs:
            link(edge_key(j, i, a), edge_key(j, i, b))

    def position(key):
        kind, j, i = key
        if kind == "h":
            va, vb = values[j, i], values[j, i + 1]
            t = (level - va) / (vb - va)
            return xs[i] + t * (xs[i + 1] - xs[i]), ys[j]
        va, vb = values[j, i], values[j + 1, i]
        t = (level - va) / (vb - va)
        return xs[i], ys[j] + t * (ys[j + 1] - ys[j])

    loops, visited = [], set()
    for start in neighbours:
        if start in visited:
            continue
        loop, previous, current = [], None, start
        while current not in visited:
            visited.add(current)
            loop.append(position(current))
            options = [key for key in neighbours[current] if key != previous]
            if not options:
                break
            previous, current = current, options[0]
        if len(loop) > 8:
            loops.append(np.array(loop))
    return loops


def resample(loop, spacing):
    closed = np.vstack([loop, loop[:1]])
    lengths = np.hypot(*np.diff(closed, axis=0).T)
    cumulative = np.concatenate([[0.0], np.cumsum(lengths)])
    count = max(16, int(cumulative[-1] / spacing))
    targets = np.linspace(0.0, cumulative[-1], count, endpoint=False)
    return np.stack([np.interp(targets, cumulative, closed[:, 0]), np.interp(targets, cumulative, closed[:, 1])], 1)


def simplify(points, tolerance):
    """Douglas–Peucker on an open polyline: straight runs collapse, curves keep detail."""
    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    direction = end - start
    length = np.hypot(*direction)
    if length < 1e-12:
        offsets = np.hypot(*(points - start).T)
    else:
        offsets = np.abs(np.cross(direction, points - start)) / length
    index = int(np.argmax(offsets))
    if offsets[index] <= tolerance:
        return np.vstack([start, end])
    left = simplify(points[: index + 1], tolerance)
    right = simplify(points[index:], tolerance)
    return np.vstack([left[:-1], right])


def simplify_loop(loop, tolerance):
    far = int(np.argmax(np.hypot(*(loop - loop[0]).T)))
    first = simplify(loop[: far + 1], tolerance)
    second = simplify(np.vstack([loop[far:], loop[:1]]), tolerance)
    return np.vstack([first[:-1], second[:-1]])


def sdf_loops(distance_fn, extent, level, resolution=900, spacing=0.004, tolerance=0.00035):
    """Iso-contours of a distance field, evenly resampled, then simplified below a pixel."""
    xs = np.linspace(-extent, extent, resolution)
    ys = np.linspace(-extent, extent, resolution)
    px, py = np.meshgrid(xs, ys)
    loops = contour_loops(distance_fn(px, py), xs, ys, level)
    return [simplify_loop(resample(loop, spacing), tolerance) for loop in loops]


def mesh_object_from_curve(name, curve, location=(0.0, 0.0, 0.0)):
    obj = bpy.data.objects.new(name + "_curve", curve)
    bpy.context.scene.collection.objects.link(obj)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    mesh.transform(Matrix.Translation(location))
    bpy.data.objects.remove(obj)
    result = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(result)
    return result


def relief(name, loops, top, height, bevel, bevel_resolution=3):
    """Flat-topped relief with rounded shoulders whose outline matches `loops` exactly."""
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "2D"
    curve.fill_mode = "BOTH"
    curve.bevel_mode = "ROUND"
    curve.bevel_depth = bevel
    curve.bevel_resolution = bevel_resolution
    curve.offset = -bevel
    curve.extrude = max(height / 2.0 - bevel, 0.0005)
    for loop in loops:
        spline = curve.splines.new("POLY")
        spline.points.add(len(loop) - 1)
        for point, (x, y) in zip(spline.points, loop):
            point.co = (float(x), float(y), 0.0, 1.0)
        spline.use_cyclic_u = True
        spline.use_smooth = True
    return mesh_object_from_curve(name, curve, (0.0, 0.0, top - height / 2.0))


def tube(name, loop, radius, z_fn):
    """Closed round tube following a 2D loop at height z_fn(x, y)."""
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.fill_mode = "FULL"
    curve.bevel_depth = radius
    curve.bevel_resolution = 4
    spline = curve.splines.new("POLY")
    spline.points.add(len(loop) - 1)
    for point, (x, y) in zip(spline.points, loop):
        point.co = (float(x), float(y), z_fn(float(x), float(y)), 1.0)
    spline.use_cyclic_u = True
    spline.use_smooth = True
    return mesh_object_from_curve(name, curve)


def finish(objects, name, material, sharp_angle=35.0):
    """Joins parts into one smooth-shaded mesh object with a single material."""
    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    with bpy.context.temp_override(active_object=objects[0], selected_editable_objects=objects):
        bpy.ops.object.join()
    obj = objects[0]
    obj.name = name
    obj.data.name = name
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    obj.data.set_sharp_from_angle(angle=math.radians(sharp_angle))
    obj.data.materials.clear()
    obj.data.materials.append(material)
    return obj


def export(objects, path):
    for obj in bpy.context.scene.objects:
        obj.select_set(obj in objects)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_yup=False,
        export_apply=True,
        export_texcoords=False,
        export_normals=True,
        export_tangents=False,
        export_materials="EXPORT",
    )


# ------------------------------------------------------------------------------- coin

FIELD_EDGE = 0.855
FIELD_Z = 0.0775  # the coin is 0.2 thick at radius 1 (10% of its diameter)
DISH = 0.006


def field_z(r):
    """Gently dished field: real coins are concave so reflections roll across the face."""
    t = min(r / FIELD_EDGE, 1.0)
    return FIELD_Z - DISH * (1.0 - t * t)


def coin_profile():
    front = [(0.0, field_z(0.0))]
    for r in (0.3, 0.55, 0.75, FIELD_EDGE):
        front.append((r, field_z(r)))
    # Inner wall of the rim, filleted top and bottom.
    front += [(0.865, 0.0785), (0.872, 0.082), (0.877, 0.089), (0.884, 0.0955), (0.893, 0.0992), (0.902, 0.1)]
    front += [(0.93, 0.1), (0.958, 0.1)]
    # Rounded outer shoulder down to the reeded band.
    centre, radius = (0.962, 0.062), 0.038
    for angle in (75, 55, 35, 15, 0):
        a = math.radians(angle)
        front.append((centre[0] + radius * math.cos(a), centre[1] + radius * math.sin(a)))
    front += [(1.0, 0.052), (1.0, 0.0)]
    back = [(r, -z) for r, z in reversed(front[:-1])]
    return front + back


def reeding(ridges, shape, depth):
    """Radius sculpt for a reeded edge: `shape` samples one ridge (0 crown → 1 groove floor)."""

    def sculpt(theta, r, z):
        if r < 0.9999:
            return r
        phase = (theta * ridges / (2.0 * math.pi)) % 1.0
        groove = shape[int(round(phase * len(shape))) % len(shape)]
        fade = 1.0 - smoothstep(0.052, 0.07, abs(z))
        return r - depth * groove * fade

    return sculpt


def rupee_distance(scale, stroke):
    """The brand ₹ stroke path (components/brand.tsx, 24-unit viewBox), centred and scaled."""

    def p(x, y):
        return ((x - 12.0) * scale, -(y - 12.0) * scale)

    strokes = [
        [p(6, 3), p(18, 3)],
        [p(6, 8), p(18, 8)],
        [p(6, 13), p(9, 13)],
        [p(*point) for point in cubic((9, 13), (15.667, 13), (15.667, 3), (9, 3))],
        [p(6, 13), p(14.5, 21)],
    ]

    def distance(px, py):
        result = np.full(px.shape, np.inf)
        for points in strokes:
            result = np.minimum(result, polyline_distance(px, py, points))
        return result

    return distance, stroke * scale / 2.0


def stripes_distance(radius=0.6, spacing=0.168, capsule=0.042):
    lines = []
    direction = np.array([1.0, 1.0]) / math.sqrt(2.0)
    normal = np.array([-1.0, 1.0]) / math.sqrt(2.0)
    for k in range(-3, 4):
        offset = k * spacing
        half = math.sqrt(max(radius * radius - offset * offset, 0.0)) - 0.07
        if half <= 0.02:
            continue
        a = normal * offset - direction * half
        b = normal * offset + direction * half
        lines.append([tuple(a), tuple(b)])

    def distance(px, py):
        result = np.full(px.shape, np.inf)
        for points in lines:
            result = np.minimum(result, polyline_distance(px, py, points))
        return result

    return distance, capsule


def build_coin(material, name, ridges, shape, depth, tolerance, bevel_resolution):
    sculpt = reeding(ridges, shape, depth)
    body = lathe(name + "_body", coin_profile(), ridges * len(shape), sculpt)
    relief_top = 0.0955
    height = relief_top - (field_z(0.0) - 0.004)

    glyph_distance, glyph_level = rupee_distance(scale=0.0515, stroke=2.3)
    glyph_loops = sdf_loops(glyph_distance, 0.66, glyph_level, tolerance=tolerance)
    front = relief(name + "_front", glyph_loops, relief_top, height, 0.0085, bevel_resolution)

    stripe_distance, stripe_level = stripes_distance()
    stripe_loops = sdf_loops(stripe_distance, 0.66, stripe_level, tolerance=tolerance)
    back = relief(name + "_back", stripe_loops, relief_top, height, 0.0085, bevel_resolution)
    back.data.transform(Matrix.Rotation(math.pi, 4, "Y"))
    return finish([body, front, back], name, material)


# ------------------------------------------------------------------------- check dome

LIP = 0.055
FACE_BULGE = 0.012
BEAD_R, BEAD_W, BEAD_H = 0.886, 0.022, 0.016


def face_z(r):
    t = min(r / 0.864, 1.0)
    return FACE_BULGE * (1.0 - t * t)


def dome_profile():
    """Face (centre outwards) → lip fillet → hemisphere down to the back pole.

    The lip fillet (radius LIP) is tangent to the face plane z = 0 and, internally, to
    the unit sphere, so its centre sits at (cx, -LIP) with |centre| = 1 - LIP.
    """
    cx = math.sqrt((1.0 - LIP) ** 2 - LIP**2)
    polar_end = math.atan2(cx, LIP)  # sphere polar angle (from -Z) at the fillet tangent
    fillet_end = math.atan2(-LIP, cx)  # the same tangent point, as an angle around the fillet centre
    face = [(0.0, face_z(0.0))]
    for r in (0.12, 0.25, 0.38, 0.5, 0.62, 0.72, 0.8, 0.864):
        face.append((r, face_z(r)))
    for index in range(1, 10):
        r = BEAD_R - BEAD_W + 2.0 * BEAD_W * index / 10.0
        face.append((r, BEAD_H * 0.5 * (1.0 + math.cos(math.pi * (r - BEAD_R) / BEAD_W))))
    face += [(0.912, 0.0), (0.926, 0.0), (cx, 0.0)]
    fillet = []
    for index in range(1, 12):
        angle = math.pi / 2.0 + (fillet_end - math.pi / 2.0) * index / 11.0
        fillet.append((cx + LIP * math.cos(angle), -LIP + LIP * math.sin(angle)))
    sphere = []
    for index in range(1, 41):
        polar = polar_end * (1.0 - index / 40.0)
        sphere.append((math.sin(polar), -math.cos(polar)))
    return face + fillet + sphere


def check_outline(stroke_radius=0.118):
    points = [(-0.4, 0.035), (-0.12, -0.245), (0.44, 0.315)]

    def distance(px, py):
        return polyline_distance(px, py, points)

    return sdf_loops(distance, 0.8, stroke_radius, spacing=0.004, tolerance=0.0003)


def build_dome(material):
    body = lathe("CheckDome_body", dome_profile(), 224)
    ridges = [tube(f"CheckDome_check{index}", loop, 0.021, lambda x, y: face_z(math.hypot(x, y)) - 0.003) for index, loop in enumerate(check_outline())]
    return finish([body, *ridges], "CheckDome", material, sharp_angle=50.0)


# ------------------------------------------------------------------------------- main


def main():
    out_dir = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    reset_scene()
    metal = metal_material("Metal")
    # Close-ups: 84 fine ridges with a flat crown and rounded groove.
    coin = build_coin(metal, "Coin", 84, (0.0, 0.18, 0.86, 1.0, 0.86, 0.18), 0.011, 0.00035, 3)
    # Small / many instances: 48 broad ridges stay legible without shimmering at ~80 px.
    lite = build_coin(metal, "CoinLite", 48, (0.0, 0.55, 1.0, 0.55), 0.013, 0.0009, 2)
    lite.location.x = 3.0  # separate nodes; the runtime reads each mesh's geometry
    export([coin, lite], out_dir / "coin.glb")

    reset_scene()
    dome = build_dome(metal_material("Metal"))
    export([dome], out_dir / "check-dome.glb")

    for path in sorted(out_dir.glob("*.glb")):
        print(f"exported {path.name} {path.stat().st_size / 1024:.0f} KiB")


main()
