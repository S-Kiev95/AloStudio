"""Build denser, evenly meshed 3D channel logos designed to stretch like rubber.

Run headless from the repo root:

    blender -b -P design/3d/build_rubber_logos.py

It reads the glyph outlines from frontend/components/ui/brand-icons.tsx (Simple
Icons, CC0), builds each logo with the same shapes and colours as
design/3d/build_logos.py, slices every part along a shared regular X/Y/Z grid
so the front face and edges deform smoothly in Three.js, and writes:

    frontend/public/brand/3d/rubber/<name>.glb   under ~250 KB each (no Draco)
    design/3d/rubber-preview.png                 a studio render of all of them
"""

import math
import os
import re
import statistics
import tempfile

import addon_utils
import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ICONS_TSX = os.path.join(ROOT, "frontend", "components", "ui", "brand-icons.tsx")
OUT_DIR = os.path.join(ROOT, "frontend", "public", "brand", "3d", "rubber")
WORK = tempfile.mkdtemp(prefix="alostudio-rubber-logos-")

# Same body/bevel proportions as build_logos.py for a 2-unit glyph.
BODY = 0.2
EDGE = 0.07
FRONT = BODY + EDGE

# Target ceiling from PLAN.logos-goma.md (~250 KB, uncompressed GLB).
MAX_GLB_BYTES = 250 * 1024


# ── helpers ──────────────────────────────────────────────────────────────────


def linear(hex_color):
    """sRGB hex -> linear RGBA for Principled BSDF."""
    h = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i : i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def material(name, hex_color="#FFFFFF", roughness=0.32, image=None):
    mat = bpy.data.materials.new(name)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = linear(hex_color)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = 0.0
    if image is not None:
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def glyph_paths():
    src = open(ICONS_TSX, encoding="utf-8").read()
    paths = dict(re.findall(r'export const (\w+) = brandIcon\(\s*"([^"]+)"', src))
    paths["Instagram"] = re.search(r'INSTAGRAM_PATH =\s*"([^"]+)"', src).group(1)
    return paths


def activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def bounds(obj):
    """World-space XY bounding box of the evaluated object."""
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    pts = [ev.matrix_world @ v.co for v in mesh.vertices]
    ev.to_mesh_clear()
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), 0))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), 0))
    return lo, hi


def transform_points(obj, fn):
    for spline in obj.data.splines:
        for p in spline.bezier_points:
            p.co, p.handle_left, p.handle_right = (
                fn(p.co),
                fn(p.handle_left),
                fn(p.handle_right),
            )
        for p in spline.points:
            v = fn(Vector(p.co[:3]))
            p.co = (v.x, v.y, v.z, 1)


def import_glyph(name, d, size=2.0):
    """Import an SVG path as a flat curve centred on the origin, `size` across."""
    svg = os.path.join(WORK, f"{name}.svg")
    with open(svg, "w", encoding="utf-8") as f:
        f.write(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'width="24" height="24"><path d="{d}"/></svg>'
        )
    before = set(bpy.data.objects)
    bpy.ops.import_curve.svg(filepath=svg)
    new = [o for o in bpy.data.objects if o not in before]
    obj = new[0]
    if len(new) > 1:
        activate(obj)
        for o in new:
            o.select_set(True)
        bpy.ops.object.join()
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    bpy.context.scene.collection.objects.link(obj)
    obj.name = name
    obj.data.materials.clear()

    lo, hi = bounds(obj)
    centre = (lo + hi) / 2
    scale = size / max(hi.x - lo.x, hi.y - lo.y)
    world = obj.matrix_world.copy()
    transform_points(obj, lambda p: (world @ Vector(p) - centre) * scale)
    obj.matrix_world.identity()
    return obj


def solid(obj, mat, depth, edge, z=0.0, grow=0.0, resolution=5, bevel_res=3):
    """Give a flat curve thickness and round edges, keeping its outline."""
    c = obj.data
    c.dimensions = "2D"
    c.fill_mode = "BOTH"
    c.extrude = depth
    c.bevel_depth = edge
    c.bevel_resolution = bevel_res
    c.offset = grow - edge
    c.resolution_u = resolution
    c.materials.clear()
    c.materials.append(mat)
    obj.location.z = z
    return obj


def duplicate(obj, name):
    copy = obj.copy()
    copy.data = obj.data.copy()
    copy.name = name
    bpy.context.scene.collection.objects.link(copy)
    return copy


def spline_area(spline):
    pts = [p.co for p in spline.bezier_points] or [p.co for p in spline.points]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def outline_only(obj, name):
    """A copy that keeps just the outer contour: the logo with holes filled."""
    copy = duplicate(obj, name)
    splines = copy.data.splines
    keep = max(range(len(splines)), key=lambda i: spline_area(splines[i]))
    for i in reversed(range(len(splines))):
        if i != keep:
            splines.remove(splines[i])
    return copy


def rounded_rect(name, w, h, r, corner_steps=14):
    curve = bpy.data.curves.new(name, "CURVE")
    pts = []
    corners = [
        (w / 2 - r, h / 2 - r, 0),
        (-w / 2 + r, h / 2 - r, 90),
        (-w / 2 + r, -h / 2 + r, 180),
        (w / 2 - r, -h / 2 + r, 270),
    ]
    for cx, cy, start in corners:
        for i in range(corner_steps + 1):
            a = math.radians(start + 90 * i / corner_steps)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    spline = curve.splines.new("POLY")
    spline.points.add(len(pts) - 1)
    for p, (x, y) in zip(spline.points, pts):
        p.co = (x, y, 0, 1)
    spline.use_cyclic_u = True
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def planar_uv(obj):
    mesh = obj.data
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    x0, y0 = min(xs), min(ys)
    w, h = max(xs) - x0, max(ys) - y0
    while mesh.uv_layers:
        mesh.uv_layers.remove(mesh.uv_layers[0])
    uv = mesh.uv_layers.new(name="UVMap")
    uv.active = True
    uv.active_render = True
    for loop in mesh.loops:
        co = mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = ((co.x - x0) / w, (co.y - y0) / h)


def grid_remesh_part(obj, xy_cuts, z_cuts=()):
    """Slice a converted curve mesh on a regular X/Y(/Z) grid for smooth bending.

    Dissolving coplanar interior edges on the front/back caps first replaces the
    long fan triangles from curve conversion with uniform interior quads while
    keeping the exact silhouette, bevel profile, and material boundaries intact.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    bm.normal_update()

    # Dissolve interior edges on flat front/back faces before bisecting.
    flat_edges = []
    flat_verts = set()
    for e in bm.edges:
        if len(e.link_faces) == 2:
            n0, n1 = e.link_faces[0].normal, e.link_faces[1].normal
            if abs(n0.z) > 0.995 and abs(n1.z) > 0.995 and n0.z * n1.z > 0:
                flat_edges.append(e)
                flat_verts.add(e.verts[0])
                flat_verts.add(e.verts[1])
    if flat_edges:
        bmesh.ops.dissolve_limit(
            bm,
            angle_limit=math.radians(0.5),
            use_dissolve_boundaries=False,
            verts=list(flat_verts),
            edges=flat_edges,
            delimit={"MATERIAL"},
        )

    # Slice along shared world-aligned X, Y, and optional Z grid planes.
    ox, oy, oz = obj.location.x, obj.location.y, obj.location.z
    for x in xy_cuts:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(
            bm,
            geom=geom,
            dist=1e-5,
            plane_co=(x - ox, 0.0, 0.0),
            plane_no=(1.0, 0.0, 0.0),
        )
    for y in xy_cuts:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(
            bm,
            geom=geom,
            dist=1e-5,
            plane_co=(0.0, y - oy, 0.0),
            plane_no=(0.0, 1.0, 0.0),
        )
    for z in z_cuts:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(
            bm,
            geom=geom,
            dist=1e-5,
            plane_co=(0.0, 0.0, z - oz),
            plane_no=(0.0, 0.0, 1.0),
        )

    # Remove only exact duplicate / degenerate elements without distorting bevels.
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
    bmesh.ops.triangulate(
        bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY"
    )
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.validate(verbose=False)
    obj.data.update()


def cut_positions(divisions, span=2.0):
    """Evenly spaced interior cut coordinates across [-span/2, +span/2]."""
    step = span / divisions
    return [-span / 2 + step * i for i in range(1, divisions)]


def mark_flat_cap_strength(obj):
    """Assign STRONG face influence to flat front/back faces for WeightedNormal.

    After slicing the flat cap into grid cells, cap triangles are small like the
    bevel strips; marking flat faces STRONG keeps their normals strictly planar
    while bevel rings blend smoothly around the rim.
    """
    mesh = obj.data
    attr = mesh.attributes.get("face_strength")
    if attr is None:
        attr = mesh.attributes.new("face_strength", "INT", "FACE")
    # Blender WeightedNormal face strength enum: 0 = WEAK, 1 = MEDIUM, 2 = STRONG.
    for poly in mesh.polygons:
        if abs(poly.normal.z) > 0.99:
            attr.data[poly.index].value = 2
        elif abs(poly.normal.z) < 0.05:
            attr.data[poly.index].value = 1
        else:
            attr.data[poly.index].value = 0


def finish(name, parts, xy_divisions=12, z_parts=(), uv_part=None):
    """Convert parts to evenly gridded smooth meshes and join into `name`."""
    xy_cuts = cut_positions(xy_divisions)
    z_cuts = (-BODY * 0.5, 0.0, BODY * 0.5)
    z_set = set(z_parts)
    for p in parts:
        activate(p)
        bpy.ops.object.convert(target="MESH")
        grid_remesh_part(p, xy_cuts, z_cuts if p in z_set else ())
        if p is uv_part:
            planar_uv(p)
        else:
            while p.data.uv_layers:
                p.data.uv_layers.remove(p.data.uv_layers[0])

    activate(parts[0])
    for p in parts:
        p.select_set(True)
    bpy.ops.object.join()
    obj = parts[0]
    obj.name = name
    obj.data.name = name
    obj.data.validate(verbose=False)

    for poly in obj.data.polygons:
        poly.use_smooth = True

    mark_flat_cap_strength(obj)
    wn = obj.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    wn.weight = 100
    wn.use_face_influence = True
    wn.keep_sharp = False
    return obj


def instagram_gradient():
    """The Instagram radial sweep at 96x96 (smooth under bilinear filtering)."""
    size = 96
    stops = [
        (0.0, "#FEDA75"),
        (0.12, "#FEDA75"),
        (0.38, "#FA7E1E"),
        (0.58, "#D62976"),
        (0.78, "#962FBF"),
        (1.0, "#4F5BD5"),
    ]
    rgb = [(t, [int(c[i : i + 2], 16) / 255 for i in (1, 3, 5)]) for t, c in stops]
    px = []
    for y in range(size):
        for x in range(size):
            u, v = x / (size - 1), y / (size - 1)
            t = min(1.0, math.hypot(u - 0.22, v + 0.08) / 1.25)
            for (t0, c0), (t1, c1) in zip(rgb, rgb[1:]):
                if t <= t1:
                    k = (t - t0) / (t1 - t0)
                    px += [c0[i] + (c1[i] - c0[i]) * k for i in range(3)] + [1.0]
                    break
    img = bpy.data.images.new("instagram-gradient", size, size)
    img.pixels = px
    img.filepath_raw = os.path.join(WORK, "instagram-gradient.png")
    img.file_format = "PNG"
    img.save()
    return img


# ── the rubber logos ─────────────────────────────────────────────────────────


def cutout(name, d, color, white, disc=False, resolution=6, xy_divisions=12):
    """Coloured badge with the mark showing through in white (Facebook, Telegram)."""
    badge = solid(
        import_glyph(name, d),
        material(name, color),
        BODY,
        EDGE,
        resolution=resolution,
        bevel_res=3,
    )
    back = (
        rounded_rect(name + "-fill", 2.0, 2.0, 1.0, corner_steps=14)
        if disc
        else outline_only(badge, name + "-fill")
    )
    fill = solid(
        back,
        white,
        BODY - 0.045,
        0.02,
        grow=-0.06,
        resolution=4,
        bevel_res=2,
    )
    return finish(
        name,
        [badge, fill],
        xy_divisions=xy_divisions,
        z_parts=(badge,),
    )


def tile(name, mat, radius=0.52):
    return solid(
        rounded_rect(name, 2.0, 2.0, radius, corner_steps=14),
        mat,
        BODY,
        EDGE,
        resolution=5,
        bevel_res=3,
    )


def bezel(name, mat, radius=0.52):
    """Pale band around a black tile so it reads on dark surfaces."""
    return solid(
        rounded_rect(name, 2.0, 2.0, radius, corner_steps=12),
        mat,
        BODY - 0.07,
        0.03,
        grow=0.05,
        resolution=4,
        bevel_res=2,
    )


def raised(name, d, mat, size, z_extra=0.0, resolution=4, bevel_res=2):
    """Thin mark standing proud of the body's front face."""
    return solid(
        import_glyph(name, d, size),
        mat,
        0.045,
        0.018,
        z=FRONT + z_extra,
        resolution=resolution,
        bevel_res=bevel_res,
    )


def build_all():
    paths = glyph_paths()
    white = material("white", "#FFFFFF", roughness=0.38)
    black = material("black", "#0B0B0D", roughness=0.25)
    pale = material("pale", "#C9CFDA", roughness=0.3)
    logos = []

    # 1. Facebook: blue disc badge with the white "f" showing through.
    logos.append(
        cutout(
            "facebook",
            paths["Facebook"],
            "#0866FF",
            white,
            disc=True,
            resolution=6,
            xy_divisions=14,
        )
    )

    # 2. Instagram: radial gradient tile, white camera on top.
    body = tile("instagram", material("instagram", image=instagram_gradient()))
    glyph = raised(
        "instagram-mark",
        paths["Instagram"],
        white,
        1.36,
        resolution=3,
        bevel_res=1,
    )
    logos.append(
        finish(
            "instagram",
            [body, glyph],
            xy_divisions=12,
            z_parts=(body,),
            uv_part=body,
        )
    )

    # 3. WhatsApp: green bubble, white ring and handset on top.
    glyph = raised(
        "whatsapp-mark",
        paths["WhatsApp"],
        white,
        2.0,
        resolution=5,
        bevel_res=2,
    )
    bubble = solid(
        outline_only(glyph, "whatsapp"),
        material("whatsapp", "#25D366"),
        BODY,
        EDGE,
        grow=0.07,
        resolution=6,
        bevel_res=3,
    )
    bubble.location.z = 0
    logos.append(
        finish(
            "whatsapp",
            [bubble, glyph],
            xy_divisions=12,
            z_parts=(bubble,),
        )
    )

    # 4. TikTok: black tile with pale bezel and cyan/red/white echoes of the note.
    body = tile("tiktok", black)
    rim = bezel("tiktok-bezel", pale)
    cyan = raised(
        "tiktok-cyan",
        paths["TikTok"],
        material("cyan", "#25F4EE"),
        1.2,
        resolution=3,
        bevel_res=1,
    )
    red = raised(
        "tiktok-red",
        paths["TikTok"],
        material("red", "#FE2C55"),
        1.2,
        z_extra=0.012,
        resolution=3,
        bevel_res=1,
    )
    note = raised(
        "tiktok-mark",
        paths["TikTok"],
        white,
        1.2,
        z_extra=0.03,
        resolution=3,
        bevel_res=1,
    )
    cyan.location.x, cyan.location.y = -0.06, 0.05
    red.location.x, red.location.y = 0.06, -0.05
    logos.append(
        finish(
            "tiktok",
            [body, rim, cyan, red, note],
            xy_divisions=10,
            z_parts=(body,),
        )
    )

    # 5. Telegram: blue disc badge with the paper plane showing through in white.
    logos.append(
        cutout(
            "telegram",
            paths["Telegram"],
            "#26A5E4",
            white,
            disc=False,
            resolution=5,
            xy_divisions=12,
        )
    )

    return logos


def export(obj):
    out_path = os.path.join(OUT_DIR, obj.name + ".glb")
    activate(obj)
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=False,
    )
    return out_path


def mesh_stats(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    verts = len(mesh.vertices)
    tris = sum(max(1, len(p.vertices) - 2) for p in mesh.polygons)
    edge_lens = [
        (mesh.vertices[e.vertices[0]].co - mesh.vertices[e.vertices[1]].co).length
        for e in mesh.edges
    ]
    med_edge = statistics.median(edge_lens) if edge_lens else 0.0
    max_edge = max(edge_lens) if edge_lens else 0.0
    ev.to_mesh_clear()
    return verts, tris, med_edge, max_edge


def render_preview(logos):
    n = len(logos)
    spacing = 2.7
    offset = (n - 1) * spacing / 2
    for i, obj in enumerate(logos):
        obj.location = (i * spacing - offset, 0.0, 0.0)
        obj.rotation_euler = (math.radians(-18), math.radians(22), 0)

    scene = bpy.context.scene
    world = bpy.data.worlds.new("world")
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.2, 0.22, 0.27, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.2
    scene.world = world

    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(35), math.radians(-25), 0)
    scene.collection.objects.link(sun)

    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 14.5
    cam.location = (0, 0, 20)
    scene.collection.objects.link(cam)
    scene.camera = cam

    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.view_settings.view_transform = "Standard"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 520
    scene.render.filepath = os.path.join(HERE, "rubber-preview.png")
    bpy.ops.render.render(write_still=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("io_curve_svg")
    os.makedirs(OUT_DIR, exist_ok=True)
    logos = build_all()

    oversized = []
    for obj in logos:
        path = export(obj)
        size = os.path.getsize(path)
        verts, tris, med_edge, max_edge = mesh_stats(obj)
        print(
            f"RUBBER {obj.name:10s}: {size / 1024:6.1f} KB | "
            f"{verts:5d} verts | {tris:5d} tris | "
            f"edge med={med_edge:.3f} max={max_edge:.3f}"
        )
        if size > MAX_GLB_BYTES:
            oversized.append((obj.name, size))

    render_preview(logos)
    if oversized:
        raise RuntimeError(f"GLB exceeds 250 KB target: {oversized}")
    print("RUBBER LOGOS OK:", ", ".join(o.name for o in logos))


main()
