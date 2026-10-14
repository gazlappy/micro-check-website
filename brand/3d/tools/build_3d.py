"""Build 3D versions of the Micro-Check logo in Blender and render sample shots.

usage:
  blender --background --python build_3d.py -- [--quick] [--only NAME ...]

Writes into brand/3d/: renders/*.png, micro-check-logo-3d.blend, *.glb, stl/*.stl
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
BRAND = os.path.dirname(OUT)
sys.path.insert(0, os.path.join(BRAND, 'fonts', 'tools'))
from pspshapes import read_shapes  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
QUICK = '--quick' in ARGS
ONLY = ARGS[ARGS.index('--only') + 1:] if '--only' in ARGS else None

PX = 0.001          # metres per logo pixel: the logo is about 1.2 m wide
CENTRE = (616, 416)  # logo pixel coordinates of the model origin


def srgb(hexcol):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    h = hexcol.lstrip('#')
    return (ch(int(h[0:2], 16)), ch(int(h[2:4], 16)), ch(int(h[4:6], 16)), 1.0)


# ------------------------------------------------------------------ scene setup

def reset():
    if bpy.app.background:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    else:
        # live session: clear the scene but keep add-ons (and the MCP connection) loaded
        for ob in list(bpy.data.objects):
            bpy.data.objects.remove(ob)
        for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.lights,
                     bpy.data.cameras, bpy.data.worlds):
            for item in list(coll):
                if item.users == 0:
                    coll.remove(item)
        for c in list(bpy.data.collections):
            bpy.data.collections.remove(c)
    sc = bpy.context.scene
    try:
        sc.render.engine = 'CYCLES'  # add-on engines aren't in the static enum list, so just try it
    except TypeError as e:
        print('Cycles unavailable, using default engine:', e)
    sc.cycles.samples = 24 if QUICK else 96
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for dev_type in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL'):
            try:
                prefs.compute_device_type = dev_type
                prefs.get_devices()
                if any(d.type != 'CPU' for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = True
                    sc.cycles.device = 'GPU'
                    print('render device', dev_type)
                    break
            except TypeError:
                continue
    except Exception as e:  # noqa: BLE001
        print('GPU setup skipped:', e)
    sc.render.resolution_x = 960 if QUICK else 1600
    sc.render.resolution_y = 600 if QUICK else 1000
    sc.render.film_transparent = False
    try:
        sc.view_settings.view_transform = 'Standard'  # keeps the brand colours true
    except TypeError:
        pass
    return sc


def material(name, base, rough=0.35, metal=0.0, emit=None, emit_strength=0.0, transmission=0.0, coat=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    inp = bsdf.inputs
    inp['Base Color'].default_value = base
    inp['Roughness'].default_value = rough
    inp['Metallic'].default_value = metal
    if 'Transmission Weight' in inp:
        inp['Transmission Weight'].default_value = transmission
    if 'Coat Weight' in inp:
        inp['Coat Weight'].default_value = coat
    if emit is not None:
        inp['Emission Color'].default_value = emit
        inp['Emission Strength'].default_value = emit_strength
    else:
        inp['Emission Strength'].default_value = 0.0
    m.diffuse_color = base
    return m


def acrylic_material():
    """Clear acrylic: see-through, with reflections that build up towards the edges."""
    m = bpy.data.materials.new('Acrylic')
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    clear = nt.nodes.new('ShaderNodeBsdfTransparent')
    clear.inputs['Color'].default_value = (0.93, 0.96, 1.0, 1)
    gloss = nt.nodes.new('ShaderNodeBsdfGlossy')
    gloss.inputs['Roughness'].default_value = 0.04
    fres = nt.nodes.new('ShaderNodeLayerWeight')
    fres.inputs['Blend'].default_value = 0.12
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(fres.outputs['Fresnel'], mix.inputs[0])
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(gloss.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    m.diffuse_color = (0.9, 0.95, 1, 0.3)
    return m


# ------------------------------------------------------------------ logo geometry

def to_xy(pt):
    return Vector(((pt[0] - CENTRE[0]) * PX, (CENTRE[1] - pt[1]) * PX, 0))


def add_spline(cu, sp):
    """sp: list of ('M', p) / ('L', p) / ('C', c1, c2, p) as read from the PSP file."""
    pts = [to_xy(sp[0][1])]
    hr, hl = [None], [None]
    for seg in sp[1:]:
        a = pts[-1]
        if seg[0] == 'L':
            b = to_xy(seg[1])
            hr[-1] = a + (b - a) / 3
            hl.append(b + (a - b) / 3)
        else:
            b = to_xy(seg[3])
            hr[-1] = to_xy(seg[1])
            hl.append(to_xy(seg[2]))
        pts.append(b)
        hr.append(None)
    if (pts[-1] - pts[0]).length < 1e-6 and len(pts) > 1:
        hl[0] = hl[-1]
        pts, hl, hr = pts[:-1], hl[:-1], hr[:-1]
    for i in range(len(pts)):
        if hl[i] is None:
            hl[i] = pts[i]
        if hr[i] is None:
            hr[i] = pts[i]
    s = cu.splines.new('BEZIER')
    s.bezier_points.add(len(pts) - 1)
    for bp, co, l, r in zip(s.bezier_points, pts, hl, hr):
        bp.handle_left_type = bp.handle_right_type = 'FREE'
        bp.co, bp.handle_left, bp.handle_right = co, l, r
    s.use_cyclic_u = True


def extrude_shapes(name, shapes, depth, bevel, face_mat, side_mat, z0=0.0):
    """Fill + extrude the shapes, convert to mesh, colour fronts and sides separately."""
    cu = bpy.data.curves.new(name + '_curve', 'CURVE')
    cu.dimensions = '2D'
    cu.fill_mode = 'BOTH'
    cu.resolution_u = 16
    cu.extrude = depth / 2
    cu.bevel_depth = bevel
    cu.bevel_resolution = 3
    for s in shapes:
        for sp in s['paths']:
            add_spline(cu, sp)
    tmp = bpy.data.objects.new(name + '_tmp', cu)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    me.name = name
    me.materials.append(face_mat)
    me.materials.append(side_mat)
    for poly in me.polygons:
        poly.material_index = 0 if poly.normal.z > 0.97 else 1  # rounded edges take the dark side colour, like the logo outline
    for poly in me.polygons:
        poly.use_smooth = poly.material_index == 1
    ob = bpy.data.objects.new(name, me)
    ob.location.z = z0 + depth / 2 + bevel
    return ob


def rounded_plate(name, w, h, depth, radius, mat):
    """A rounded-corner panel (extruded curve, so the geometry stays clean), front face at z=0."""
    k = 0.5523
    hw, hh = w / 2, h / 2
    corners = [Vector((hw, -hh, 0)), Vector((hw, hh, 0)), Vector((-hw, hh, 0)), Vector((-hw, -hh, 0))]
    pts = []  # (co, handle_left, handle_right)
    for i, c in enumerate(corners):
        prev, nxt = corners[i - 1], corners[(i + 1) % 4]
        a = c + (prev - c).normalized() * radius   # arriving along the previous edge
        b = c + (nxt - c).normalized() * radius    # leaving along the next edge
        pts.append([a, None, a + (c - a) * k])
        pts.append([b, b + (c - b) * k, None])
    for i in range(len(pts)):
        if pts[i][2] is None:
            nxt = pts[(i + 1) % len(pts)]
            pts[i][2] = pts[i][0] + (nxt[0] - pts[i][0]) / 3
            nxt[1] = nxt[0] + (pts[i][0] - nxt[0]) / 3
    bevel = min(depth * 0.2, 0.004)
    cu = bpy.data.curves.new(name + '_curve', 'CURVE')
    cu.dimensions = '2D'
    cu.fill_mode = 'BOTH'
    cu.resolution_u = 16
    cu.extrude = depth / 2 - bevel
    cu.bevel_depth = bevel
    cu.bevel_resolution = 4
    sp = cu.splines.new('BEZIER')
    sp.bezier_points.add(len(pts) - 1)
    for bp, (co, hl, hr) in zip(sp.bezier_points, pts):
        bp.handle_left_type = bp.handle_right_type = 'FREE'
        bp.co, bp.handle_left, bp.handle_right = co, hl, hr
    sp.use_cyclic_u = True
    tmp = bpy.data.objects.new(name + '_tmp', cu)
    bpy.context.scene.collection.objects.link(tmp)
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    me.name = name
    me.materials.append(mat)
    for poly in me.polygons:
        poly.use_smooth = abs(poly.normal.z) < 0.6
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location.z = -depth / 2
    return ob


def build_logo(col, black_words=False, freestanding=False):
    shapes = read_shapes(os.path.join(BRAND, 'vectorlogo.psp'))
    tick = [s for s in shapes if s['fill'] == '#c7e0eb']
    micro = [s for s in shapes if s['fill'] == '#ff0000']
    white = [s for s in shapes if s['fill'] == '#ffffff']
    check = [s for s in white if s['bbox'][1] < 600]
    computers = [s for s in white if s['bbox'][1] >= 600]

    side = material('Letter sides', srgb('#111111'), rough=0.45)
    red = material('Micro red', srgb('#ff0000'), rough=0.5, coat=0.12)
    words = material('Check face', srgb('#0b0b0b') if black_words else srgb('#ededed'), rough=0.45, coat=0.12)
    tick_face = material('Tick face', srgb('#c7e0eb'), rough=0.45, coat=0.1)
    tick_side = material('Tick sides', srgb('#4040ff'), rough=0.4)

    if freestanding:
        # deeper letters, and a solid tick that sits back from the lettering
        objs = [
            extrude_shapes('Tick', tick, 0.032, 0.003, tick_face, tick_side, z0=-0.03),
            extrude_shapes('MICRO', micro, 0.075, 0.003, red, side),
            extrude_shapes('CHECK', check, 0.065, 0.003, words, side),
            extrude_shapes('COMPUTERS', computers, 0.04, 0.0015, words, side),
        ]
    else:
        objs = [
            extrude_shapes('Tick', tick, 0.014, 0.0015, tick_face, tick_side),
            extrude_shapes('MICRO', micro, 0.055, 0.002, red, side),
            extrude_shapes('CHECK', check, 0.045, 0.002, words, side),
            extrude_shapes('COMPUTERS', computers, 0.028, 0.0012, words, side),
        ]
    for o in objs:
        col.objects.link(o)
    return objs


# ------------------------------------------------------------------ staging

def look_at(ob, target, up=(0, 1, 0)):
    """Point -Z at the target, keeping 'up' (world) at the top of the frame."""
    from mathutils import Matrix
    f = (Vector(target) - ob.location).normalized()
    r = f.cross(Vector(up))
    if r.length < 1e-6:
        r = f.cross(Vector((0, 0, 1)))
    r.normalize()
    u = r.cross(f)
    ob.rotation_euler = Matrix((r, u, -f)).transposed().to_euler()


def camera(loc, target, lens=50, up=(0, 1, 0)):
    cam = bpy.data.cameras.new('Camera')
    cam.lens = lens
    ob = bpy.data.objects.new('Camera', cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    look_at(ob, target, up)
    bpy.context.scene.camera = ob
    return ob


def area_light(name, loc, target, power, size, colour=(1, 1, 1)):
    li = bpy.data.lights.new(name, 'AREA')
    li.energy = power
    li.size = size
    li.color = colour
    ob = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    look_at(ob, target)
    return ob


def world(colour, strength):
    w = bpy.data.worlds.new('World')
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = colour
    bg.inputs['Strength'].default_value = strength
    bpy.context.scene.world = w


def plane(name, size, loc, rot, mat):
    bpy.ops.mesh.primitive_plane_add(size=size, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


def render(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    print('rendered', path)


# ------------------------------------------------------------------ the sample shots

def shot_wall_sign():
    """Daytime: purple sign panel on a painted wall."""
    reset()
    col = bpy.context.scene.collection
    build_logo(col)
    rounded_plate('Sign panel', 1.34, 0.9, 0.035, 0.05, material('Brand purple', srgb('#6633cc'), rough=0.5, coat=0.15))
    plane('Wall', 12, (0, 0, -0.036), (0, 0, 0), material('Wall', srgb('#b8b1a6'), rough=0.9))
    world(srgb('#cfd6e0'), 0.1)
    area_light('Key', (-1.4, 2.2, 1.3), (0, 0, 0), 220, 2.4, (1, 0.97, 0.92))
    area_light('Fill', (2.2, -0.4, 1.2), (0, 0, 0), 60, 3.0, (0.9, 0.95, 1))
    camera((0.95, -0.75, 2.05), (0.03, -0.02, 0), lens=42)
    render(os.path.join(OUT, 'renders', 'micro-check-3d-wall-sign.png'))


def shot_night_sign():
    """Night: illuminated channel letters on a dark shop front."""
    reset()
    col = bpy.context.scene.collection
    build_logo(col)
    glow = {'Micro red': ('#ff1010', 2.4), 'Check face': ('#ffffff', 1.5), 'Tick face': ('#3d8bff', 1.6)}
    for mname, (hexc, strength) in glow.items():
        m = bpy.data.materials[mname]
        bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Emission Color'].default_value = srgb(hexc)
        bsdf.inputs['Emission Strength'].default_value = strength
        bsdf.inputs['Base Color'].default_value = srgb(hexc)
    rounded_plate('Sign panel', 1.34, 0.9, 0.035, 0.05, material('Dark panel', srgb('#1d0f3a'), rough=0.35, coat=0.8))
    plane('Wall', 12, (0, 0, -0.036), (0, 0, 0), material('Wall night', srgb('#2a2a30'), rough=0.9))
    world(srgb('#0a0c18'), 0.25)
    area_light('Moon', (2.5, -1.5, 2.5), (0, 0, 0), 120, 3, (0.6, 0.7, 1))
    camera((-0.85, -0.55, 2.1), (-0.02, -0.02, 0), lens=42)
    render(os.path.join(OUT, 'renders', 'micro-check-3d-night-sign.png'))


def shot_desk():
    """Desk ornament: black CHECK/COMPUTERS on clear acrylic, standing on a desk."""
    reset()
    col = bpy.data.collections.new('Logo')
    bpy.context.scene.collection.children.link(col)
    objs = build_logo(col, black_words=True)
    acrylic = rounded_plate('Acrylic', 1.3, 0.86, 0.02, 0.03, acrylic_material())
    acrylic.visible_shadow = False  # clear acrylic shouldn't cast a solid shadow
    for c in acrylic.users_collection:
        c.objects.unlink(acrylic)
    col.objects.link(acrylic)
    rig = bpy.data.objects.new('Logo rig', None)
    bpy.context.scene.collection.objects.link(rig)
    for o in objs + [acrylic]:
        o.parent = rig
    rig.rotation_euler = (math.radians(90), 0, 0)
    rig.location = (0, 0, 0.43 + 0.06)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.02, 0.03))
    base = bpy.context.active_object
    base.name = 'Base'
    base.scale = (1.4, 0.22, 0.06)
    bev = base.modifiers.new('bevel', 'BEVEL')
    bev.width = 0.012
    bev.segments = 4
    base.data.materials.append(material('Base black', srgb('#151515'), rough=0.25, coat=0.5))
    plane('Desk', 14, (0, 0, 0), (0, 0, 0), material('Desk', srgb('#8a6a4a'), rough=0.45))
    plane('Backdrop', 14, (0, 3, 0), (math.radians(90), 0, 0), material('Backdrop', srgb('#d9d4cc'), rough=0.9))
    world(srgb('#d8dde6'), 0.15)
    area_light('Key', (-1.8, -1.6, 2.2), (0, 0, 0.45), 320, 2.0, (1, 0.96, 0.9))
    area_light('Rim', (1.6, 1.2, 1.6), (0, 0, 0.45), 180, 1.5, (0.85, 0.9, 1))
    camera((1.15, -2.1, 0.75), (0, 0, 0.45), lens=48, up=(0, 0, 1))
    render(os.path.join(OUT, 'renders', 'micro-check-3d-desk.png'))


# ------------------------------------------------------------------ model files

def export_models():
    """Plain model (no scenery) for 3D viewers, printing and further work."""
    reset()
    col = bpy.context.scene.collection
    objs = build_logo(col)
    plate = rounded_plate('Sign panel', 1.34, 0.9, 0.035, 0.05, material('Brand purple', srgb('#6633cc'), rough=0.3, coat=0.8))
    for o in [plate]:
        for m in o.modifiers:
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.modifier_apply(modifier=m.name)
    world(srgb('#cfd6e0'), 1.0)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'micro-check-logo-3d.blend'), compress=True)

    def select(objects):
        bpy.ops.object.select_all(action='DESELECT')
        for o in objects:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]

    select(objs)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, 'micro-check-logo-3d.glb'), use_selection=True, export_apply=True)
    select(objs + [plate])
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, 'micro-check-logo-3d-plaque.glb'), use_selection=True, export_apply=True)

    # STL for 3D printing: 200 mm wide plaque, plus one file per colour for multi-colour printers
    os.makedirs(os.path.join(OUT, 'stl'), exist_ok=True)
    scale = 200 / 1.34 * 1.0  # Blender metres -> printer millimetres
    stl = getattr(bpy.ops.wm, 'stl_export', None)
    parts = {'plaque-complete': objs + [plate], 'part-purple-panel': [plate], 'part-red-micro': [objs[1]],
             'part-white-check-computers': [objs[2], objs[3]], 'part-blue-tick': [objs[0]]}
    for fname, group in parts.items():
        select(group)
        path = os.path.join(OUT, 'stl', 'micro-check-%s.stl' % fname)
        stl(filepath=path, export_selected_objects=True, global_scale=scale, apply_modifiers=True, ascii_format=False)
        print('stl', path)


# ------------------------------------------------------------------ freestanding logo (no panel)

FRAMES = 36  # length of the sway animation loop


def stage_freestanding(black_words=False):
    """Letters and tick standing upright on an invisible floor that only keeps the shadow."""
    sc = reset()
    sc.render.film_transparent = True
    col = bpy.data.collections.new('Logo')
    sc.collection.children.link(col)
    objs = build_logo(col, black_words=black_words, freestanding=True)
    rig = bpy.data.objects.new('Logo', None)
    sc.collection.objects.link(rig)
    for o in objs:
        o.parent = rig
    rig.rotation_euler = (math.radians(90), 0, 0)
    rig.location = (0, 0, 0.392)  # bottom of COMPUTERS on the floor
    floor = plane('Shadow floor', 20, (0, 0, 0), (0, 0, 0), material('Floor', (0.8, 0.8, 0.8, 1), rough=0.6))
    floor.is_shadow_catcher = True
    floor.visible_glossy = False  # keep the white floor out of the letters' reflections
    world(srgb('#c9ced8'), 0.12)
    for m in ('Letter sides',):
        bsdf = next(n for n in bpy.data.materials[m].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = srgb('#0a0a0c')
        bsdf.inputs['Roughness'].default_value = 0.5
    area_light('Key', (-2.2, -2.4, 2.6), (0, 0, 0.4), 240, 2.2, (1, 0.97, 0.92))
    area_light('Fill', (2.6, -1.8, 1.2), (0, 0, 0.4), 60, 3.0, (0.9, 0.95, 1))
    area_light('Rim', (0.8, 2.4, 2.0), (0, 0, 0.4), 260, 1.6, (0.85, 0.9, 1))
    area_light('Front', (0, -3.2, 0.5), (0, 0, 0.4), 45, 2.5)
    sc.world.cycles_visibility.glossy = False  # letter sides stay black instead of mirroring the sky
    return rig, objs


def shot_free_hero():
    stage_freestanding()
    camera((-1.25, -2.35, 0.95), (0.02, 0, 0.4), lens=50, up=(0, 0, 1))
    render(os.path.join(OUT, 'renders', 'micro-check-3d-logo-angle.png'))


def shot_free_front():
    stage_freestanding()
    camera((0, -2.9, 0.62), (0, 0, 0.41), lens=55, up=(0, 0, 1))
    render(os.path.join(OUT, 'renders', 'micro-check-3d-logo-front.png'))


def shot_free_black():
    stage_freestanding(black_words=True)
    camera((1.25, -2.35, 0.95), (-0.02, 0, 0.4), lens=50, up=(0, 0, 1))
    render(os.path.join(OUT, 'renders', 'micro-check-3d-logo-black-angle.png'))


def turntable(start=0, end=FRAMES):
    """Render frames of a gentle sway (about +/-32 degrees) as transparent PNGs."""
    rig, _ = stage_freestanding()
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 900, 600
    sc.cycles.samples = 48
    camera((0, -2.9, 0.75), (0, 0, 0.41), lens=52, up=(0, 0, 1))
    folder = os.path.join(OUT, 'renders', 'turntable')
    os.makedirs(folder, exist_ok=True)
    for f in range(start, end):
        rig.rotation_euler.z = math.radians(32) * math.sin(2 * math.pi * f / FRAMES)
        render(os.path.join(folder, 'frame_%03d.png' % f))


def export_freestanding():
    """Model files of the letters and tick only, standing upright."""
    rig, objs = stage_freestanding()
    bpy.data.objects.remove(bpy.data.objects['Shadow floor'])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'micro-check-logo-3d.blend'), compress=True)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs + [rig]:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, 'micro-check-logo-3d.glb'), use_selection=True, export_apply=True)
    for fmt, op in (('obj', getattr(bpy.ops.wm, 'obj_export', None)),):
        if op:
            op(filepath=os.path.join(OUT, 'micro-check-logo-3d.obj'), export_selected_objects=True,
               export_materials=True, apply_modifiers=True)
    print('exported freestanding model')


# ------------------------------------------------------------------ double-sided logo

def poly_core(name, pts_px, depth, mat):
    """Extrude the outline from core_outline.json into the slim core between the two faces."""
    cu = bpy.data.curves.new(name + '_curve', 'CURVE')
    cu.dimensions = '2D'
    cu.fill_mode = 'BOTH'
    bevel = min(depth * 0.25, 0.004)
    cu.extrude = depth / 2 - bevel
    cu.bevel_depth = bevel
    cu.bevel_resolution = 4
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts_px) - 1)
    for pt, (x, y) in zip(sp.points, pts_px):
        v = to_xy((x, y))
        pt.co = (v.x, v.y, 0, 1)
    sp.use_cyclic_u = True
    tmp = bpy.data.objects.new(name + '_tmp', cu)
    bpy.context.scene.collection.objects.link(tmp)
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    me.name = name
    me.materials.append(mat)
    for poly in me.polygons:
        poly.use_smooth = abs(poly.normal.z) < 0.9
    return bpy.data.objects.new(name, me)


def build_double(col):
    """Core + logo on the front + the same logo turned round on the back. Returns (rig, parts)."""
    import json
    shapes = read_shapes(os.path.join(BRAND, 'vectorlogo.psp'))
    tick = [s for s in shapes if s['fill'] == '#c7e0eb']
    micro = [s for s in shapes if s['fill'] == '#ff0000']
    white = [s for s in shapes if s['fill'] == '#ffffff']
    check = [s for s in white if s['bbox'][1] < 600]
    computers = [s for s in white if s['bbox'][1] >= 600]

    side = material('Letter sides', srgb('#0a0a0c'), rough=0.5)
    red = material('Micro red', srgb('#ff0000'), rough=0.5, coat=0.12)
    words = material('Check face', srgb('#ededed'), rough=0.45, coat=0.12)
    tick_face = material('Tick face', srgb('#c7e0eb'), rough=0.45, coat=0.1)
    tick_side = material('Tick sides', srgb('#4040ff'), rough=0.4)
    core_mat = material('Core', srgb('#101014'), rough=0.35, coat=0.4)

    core_depth = 0.026
    half = core_depth / 2
    outline = json.load(open(os.path.join(HERE, 'core_outline.json')))
    parts = [poly_core('Core', outline, core_depth, core_mat)]
    for side_name, turn in (('Front', 0.0), ('Back', math.pi)):
        objs = [
            extrude_shapes('Tick ' + side_name, tick, 0.012, 0.002, tick_face, tick_side, z0=half - 0.002),
            extrude_shapes('MICRO ' + side_name, micro, 0.04, 0.0025, red, side, z0=half - 0.002),
            extrude_shapes('CHECK ' + side_name, check, 0.034, 0.0025, words, side, z0=half - 0.002),
            extrude_shapes('COMPUTERS ' + side_name, computers, 0.022, 0.0015, words, side, z0=half - 0.002),
        ]
        if turn:
            # the back copy is the front turned half way round, so it reads correctly from behind
            for o in objs:
                o.location = (-o.location.x, o.location.y, -o.location.z)
                o.rotation_euler = (0, turn, 0)
        parts += objs
    rig = bpy.data.objects.new('Micro-Check logo (double-sided)', None)
    rig.empty_display_size = 0.3
    bpy.context.scene.collection.objects.link(rig)
    for o in parts:
        col.objects.link(o)
        o.parent = rig
    rig.rotation_euler = (math.radians(90), 0, 0)
    return rig, parts


def stage_double():
    sc = reset()
    sc.render.film_transparent = True
    col = bpy.data.collections.new('Logo')
    sc.collection.children.link(col)
    rig, parts = build_double(col)
    rig.location = (0, 0, 0.46)
    floor = plane('Shadow floor', 20, (0, 0, 0), (0, 0, 0), material('Floor', (0.8, 0.8, 0.8, 1), rough=0.6))
    floor.is_shadow_catcher = True
    floor.visible_glossy = False
    world(srgb('#c9ced8'), 0.12)
    sc.world.cycles_visibility.glossy = False
    # lit from both sides so the back looks as good as the front
    for y in (-1, 1):
        area_light('Key%+d' % y, (-2.2 * y, 2.4 * y, 2.6), (0, 0, 0.45), 240, 2.2, (1, 0.97, 0.92))
        area_light('Fill%+d' % y, (2.6 * y, 1.8 * y, 1.2), (0, 0, 0.45), 60, 3.0, (0.9, 0.95, 1))
        area_light('Front%+d' % y, (0, 3.2 * y, 0.5), (0, 0, 0.45), 45, 2.5)
    return rig, parts


def shot_double(view):
    stage_double()
    cams = {'front': ((0, -3.0, 0.7), (0, 0, 0.45)),
            'back': ((0, 3.0, 0.7), (0, 0, 0.45)),
            'angle': ((-1.6, -2.4, 1.0), (0, 0, 0.45))}
    loc, target = cams[view]
    camera(loc, target, lens=50, up=(0, 0, 1))
    render(os.path.join(OUT, 'renders', 'micro-check-3d-double-%s.png' % view))


def spin(start=0, end=36, frames=36):
    """Full turn, transparent frames: the logo reads correctly the whole way round."""
    rig, _ = stage_double()
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 900, 600
    sc.cycles.samples = 48
    camera((0, -3.0, 0.8), (0, 0, 0.45), lens=50, up=(0, 0, 1))
    folder = os.path.join(OUT, 'renders', 'spin')
    os.makedirs(folder, exist_ok=True)
    for f in range(start, end):
        rig.rotation_euler.z = 2 * math.pi * f / frames
        render(os.path.join(folder, 'frame_%03d.png' % f))


def export_double():
    rig, parts = stage_double()
    rig.location = (0, 0, 0)
    bpy.data.objects.remove(bpy.data.objects['Shadow floor'])
    path = os.path.join(OUT, 'micro-check-logo-3d-double-sided')
    bpy.ops.wm.save_as_mainfile(filepath=path + '.blend', compress=True)
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts + [rig]:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.export_scene.gltf(filepath=path + '.glb', use_selection=True, export_apply=True)
    print('exported', path)


JOBS = {'hero': shot_free_hero, 'front': shot_free_front, 'black': shot_free_black,
        'turntable': turntable, 'export_free': export_freestanding,
        'wall': shot_wall_sign, 'night': shot_night_sign, 'desk': shot_desk, 'export': export_models}

if __name__ == '__main__':
    os.makedirs(os.path.join(OUT, 'renders'), exist_ok=True)
    for name, job in JOBS.items():
        if ONLY and name not in ONLY:
            continue
        print('==', name)
        job()
    print('done')
