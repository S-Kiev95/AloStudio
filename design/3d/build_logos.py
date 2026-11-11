"""Build the 3D channel logos that float on the login screen.

Run headless from the repo root:

    blender -b -P design/3d/build_logos.py

It reads the glyph outlines from frontend/components/ui/brand-icons.tsx (Simple
Icons, CC0), models each logo as a thick rubbery solid, and writes:

    frontend/public/brand/3d/<name>.glb   one per logo, what the app loads
    design/3d/logos.blend                 the scene, to open and tweak
    design/3d/preview.png                 a render of all of them
"""

import math
import os
import re
import tempfile

import addon_utils
import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ICONS_TSX = os.path.join(ROOT, "frontend", "components", "ui", "brand-icons.tsx")
OUT_DIR = os.path.join(ROOT, "frontend", "public", "brand", "3d")
WORK = tempfile.mkdtemp(prefix="alostudio-logos-")

# Half depth of a logo body and the roundness of its edges, for a glyph that
# spans 2 units.
BODY = 0.2
EDGE = 0.07
FRONT = BODY + EDGE


# ── helpers ──────────────────────────────────────────────────────────────────


def linear(hex_color):
    """sRGB hex -> linear RGBA, which is what Principled BSDF takes."""
    h = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i : i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def material(name, hex_color="#FFFFFF", roughness=0.32, image=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
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
    """World-space bounding box of the evaluated object."""
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
    """The SVG path as a flat curve centred on the origin, `size` across."""
    svg = os.path.join(WORK, f"{name}.svg")
    with open(svg, "w") as f:
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


def solid(obj, mat, depth, edge, z=0.0, grow=0.0, resolution=6):
    """Give a flat curve thickness and round edges, keeping its outline."""
    c = obj.data
    c.dimensions = "2D"
    c.fill_mode = "BOTH"
    c.extrude = depth
    c.bevel_depth = edge
    c.bevel_resolution = 3
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


def rounded_rect(name, w, h, r):
    curve = bpy.data.curves.new(name, "CURVE")
    pts = []
    corners = [
        (w / 2 - r, h / 2 - r, 0),
        (-w / 2 + r, h / 2 - r, 90),
        (-w / 2 + r, -h / 2 + r, 180),
        (w / 2 - r, -h / 2 + r, 270),
    ]
    steps = 16
    for cx, cy, start in corners:
        for i in range(steps + 1):
            a = math.radians(start + 90 * i / steps)
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
    uv = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        co = mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = ((co.x - x0) / w, (co.y - y0) / h)


def finish(name, parts, uv_part=None):
    """Curves -> one smooth mesh object named `name`."""
    for p in parts:
        activate(p)
        bpy.ops.object.convert(target="MESH")
        if p is uv_part:
            planar_uv(p)
    activate(parts[0])
    for p in parts:
        p.select_set(True)
    bpy.ops.object.join()
    obj = parts[0]
    obj.name = name
    obj.data.name = name
    for poly in obj.data.polygons:
        poly.use_smooth = True
    # Flat faces stay flat and only the rounded edges blend.
    wn = obj.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    wn.weight = 100
    wn.keep_sharp = False
    return obj


def instagram_gradient():
    """The Instagram glow: a radial sweep from the bottom-left corner."""
    size = 256
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


# ── the logos ────────────────────────────────────────────────────────────────


def cutout(name, d, color, white, disc=False):
    """A coloured badge with the mark showing through in white (Telegram,
    Facebook, Messenger): the Simple Icons outline is the badge minus the mark."""
    badge = solid(import_glyph(name, d), material(name, color), BODY, EDGE)
    # Facebook's "f" runs off the badge's edge, so its outline has no hole to
    # fill: it takes a plain disc instead.
    back = (
        rounded_rect(name + "-fill", 2.0, 2.0, 1.0)
        if disc
        else outline_only(badge, name + "-fill")
    )
    fill = solid(back, white, BODY - 0.045, 0.02, grow=-0.06)
    return finish(name, [badge, fill])


def tile(name, mat, radius=0.52):
    return solid(rounded_rect(name, 2.0, 2.0, radius), mat, BODY, EDGE)


def bezel(name, mat, radius=0.52):
    """A pale band around a black tile, so it reads on a dark page."""
    return solid(
        rounded_rect(name, 2.0, 2.0, radius), mat, BODY - 0.07, 0.03, grow=0.05
    )


def gmail_mark(d, size, mats):
    """Gmail's "M", split into its five colours: the V, the two bars and the
    two top corners. `mats` is in that order."""
    obj = solid(import_glyph("gmail-mark", d, size), mats[0], 0.05, 0.018, z=FRONT)
    activate(obj)
    bpy.ops.object.convert(target="MESH")
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    def cut(co, no):
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no)

    # The bars are 5.455 of the icon's 24 units wide.
    bar = size * (0.5 - 5.455 / 24)
    cut((-bar, 0, 0), (1, 0, 0))
    cut((bar, 0, 0), (1, 0, 0))
    # Each bar ends on a slant: the underside of the V carried on to the outer
    # edge. Above it is the corner. In the icon the V meets the bar from 4.64
    # (its top, the highest point on the cut) down to 11.73.
    top = max(v.co.y for v in bm.verts if abs(abs(v.co.x) - bar) < 1e-4)
    low = top - (11.73 - 4.64) / 24 * size
    left_n = Vector((0.75, 1, 0))
    right_n = Vector((-0.75, 1, 0))
    left_p = Vector((-bar, low, 0))
    right_p = Vector((bar, low, 0))
    cut(left_p, left_n)
    cut(right_p, right_n)
    for face in bm.faces:
        c = face.calc_center_median()
        if c.x < -bar:
            face.material_index = 3 if (c - left_p).dot(left_n) > 0 else 1
        elif c.x > bar:
            face.material_index = 4 if (c - right_p).dot(right_n) > 0 else 2
    bm.to_mesh(obj.data)
    bm.free()
    for m in mats[1:]:
        obj.data.materials.append(m)
    return obj


def raised(name, d, mat, size, z_extra=0.0):
    """The mark as a thin slab standing proud of the body's front face."""
    return solid(
        import_glyph(name, d, size), mat, 0.045, 0.018, z=FRONT + z_extra
    )


def build_all():
    paths = glyph_paths()
    white = material("white", "#FFFFFF", roughness=0.38)
    logos = []

    # WhatsApp: green bubble, white ring and handset on top.
    glyph = raised("whatsapp-mark", paths["WhatsApp"], white, 2.0)
    bubble = solid(
        outline_only(glyph, "whatsapp"),
        material("whatsapp", "#25D366"),
        BODY,
        EDGE,
        grow=0.07,
    )
    bubble.location.z = 0
    logos.append(finish("whatsapp", [bubble, glyph]))

    # Instagram: gradient tile, white camera on top.
    body = tile("instagram", material("instagram", image=instagram_gradient()))
    glyph = raised("instagram-mark", paths["Instagram"], white, 1.36)
    logos.append(finish("instagram", [body, glyph], uv_part=body))

    logos.append(cutout("facebook", paths["Facebook"], "#0866FF", white, disc=True))
    logos.append(cutout("telegram", paths["Telegram"], "#26A5E4", white))
    logos.append(cutout("messenger", paths["Messenger"], "#0084FF", white))

    # LinkedIn: blue tile, white "in". The icon is the tile minus the letters,
    # so dropping its outer contour leaves the letters.
    body = tile("linkedin", material("linkedin", "#0A66C2"), radius=0.3)
    letters = import_glyph("linkedin-mark", paths["LinkedIn"], 2.0)
    splines = letters.data.splines
    splines.remove(max(splines, key=spline_area))
    solid(letters, white, 0.045, 0.018, z=FRONT)
    logos.append(finish("linkedin", [body, letters]))

    # X and Threads: black tile with a pale band, white mark.
    black = material("black", "#0B0B0D", roughness=0.25)
    pale = material("pale", "#C9CFDA", roughness=0.3)
    for name, key, size in (("x", "XLogo", 1.18), ("threads", "Threads", 1.3)):
        body = tile(name, black)
        glyph = raised(name + "-mark", paths[key], white, size)
        logos.append(finish(name, [body, bezel(name + "-bezel", pale), glyph]))

    # TikTok: black tile, the note in white over its cyan and red echoes.
    body = tile("tiktok", black)
    cyan = raised("tiktok-cyan", paths["TikTok"], material("cyan", "#25F4EE"), 1.2)
    red = raised(
        "tiktok-red", paths["TikTok"], material("red", "#FE2C55"), 1.2, z_extra=0.012
    )
    note = raised("tiktok-mark", paths["TikTok"], white, 1.2, z_extra=0.03)
    cyan.location.x, cyan.location.y = -0.06, 0.05
    red.location.x, red.location.y = 0.06, -0.05
    logos.append(
        finish("tiktok", [body, bezel("tiktok-bezel", pale), cyan, red, note])
    )

    # Gmail: white envelope, the five-colour "M" on top.
    body = solid(rounded_rect("gmail", 2.0, 1.62, 0.3), white, BODY, EDGE)
    mark = gmail_mark(
        paths["Gmail"],
        1.5,
        [
            material("gmail-red", "#EA4335"),
            material("gmail-blue", "#4285F4"),
            material("gmail-green", "#34A853"),
            material("gmail-darkred", "#C5221F"),
            material("gmail-yellow", "#FBBC04"),
        ],
    )
    logos.append(finish("gmail", [body, mark]))

    return logos


def export(obj):
    activate(obj)
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(OUT_DIR, obj.name + ".glb"),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        # Keep Blender's axes: the logo faces +Z, which is the web camera.
        export_yup=False,
    )


def render_preview(logos):
    cols = 6
    for i, obj in enumerate(logos):
        obj.location = ((i % cols - 2.5) * 2.7, (0.5 - i // cols) * 2.7, 0)
        obj.rotation_euler = (math.radians(-18), math.radians(22), 0)
    scene = bpy.context.scene
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.2, 0.22, 0.27, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.2
    scene.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(35), math.radians(-25), 0)
    scene.collection.objects.link(sun)
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 17
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
    scene.render.resolution_y = 800
    scene.render.filepath = os.path.join(HERE, "preview.png")
    bpy.ops.render.render(write_still=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("io_curve_svg")
    os.makedirs(OUT_DIR, exist_ok=True)
    logos = build_all()
    for obj in logos:
        export(obj)
    render_preview(logos)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "logos.blend"))
    print("LOGOS OK:", ", ".join(o.name for o in logos))


main()
