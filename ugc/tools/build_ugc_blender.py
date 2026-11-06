"""
JaKing Lunar Colony Collection - 3D UGC accessories (Blender build script).

Builds 6 original rigid accessories procedurally, each as ONE mesh with ONE
256x256 palette texture (Roblox-friendly), then exports FBX (for Roblox Studio)
and GLB (for the web gallery) and renders previews on a blocky avatar.

Run inside Blender (Scripting tab -> Run Script), or via the Blender MCP.
Call  run("build")  then  run("render", item)  for each item and  run("lineup").

Units: 1 Blender unit = 1 Roblox stud. When importing to Roblox Studio
(File > Import 3D) set File Dimensions > Scale Unit to "Stud".
Avatar reference used for placement: torso 2x1x2 centred at z=1, head ~1.2
centred at z=2.6 (top of head z=3.2). Character faces -Y.
"""
import bpy, bmesh, math, os
from mathutils import Matrix, Vector, Euler

OUT = os.path.join(os.environ.get("OneDrive") or os.path.expanduser("~"), "Roblox", "LunarColonyUGC")
os.makedirs(OUT, exist_ok=True)

# ----------------------------------------------------------- palette ----
PAL = [  # (sRGB hex, emissive 0/1)
    ("#f4f7fb", 0),  # 0 white plate
    ("#13254a", 0),  # 1 navy
    ("#9aa6b5", 0),  # 2 silver
    ("#22e3ff", 1),  # 3 cyan glow
    ("#1a1450", 0),  # 4 indigo
    ("#ffd36b", 1),  # 5 star gold glow
    ("#d4a52c", 0),  # 6 gold metal
    ("#3d7bff", 1),  # 7 blue glow
    ("#0b0c10", 0),  # 8 black
    ("#39ff88", 1),  # 9 neon green
    ("#15171c", 0),  # 10 charcoal
    ("#a64dff", 1),  # 11 purple glow
    ("#06030d", 0),  # 12 void black
    ("#ffffff", 1),  # 13 white glow
    ("#2b2470", 0),  # 14 deep violet
    ("#1fae9a", 0),  # 15 teal metal
    ("#c88bff", 1),  # 16 lilac glow
    ("#5b6472", 0),  # 17 gunmetal
]
GRID, TEX = 8, 256
CELL = TEX // GRID


def hex2rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def make_images():
    def img(name, colorspace):
        im = bpy.data.images.get(name)
        if im:
            bpy.data.images.remove(im)
        im = bpy.data.images.new(name, TEX, TEX, alpha=False)
        im.colorspace_settings.name = colorspace
        return im
    pal, emit = img("LC_palette", "sRGB"), img("LC_emit", "Non-Color")
    px = [0.5, 0.5, 0.5, 1.0] * (TEX * TEX)
    ep = [0.0, 0.0, 0.0, 1.0] * (TEX * TEX)
    for i, (h, e) in enumerate(PAL):
        r, g, b = hex2rgb(h)
        col, row = i % GRID, i // GRID
        for y in range(row * CELL, (row + 1) * CELL):
            for x in range(col * CELL, (col + 1) * CELL):
                k = (y * TEX + x) * 4
                px[k:k + 3] = [r, g, b]
                ep[k:k + 3] = [e, e, e]
    pal.pixels = px
    emit.pixels = ep
    pal.filepath_raw = os.path.join(OUT, "lunar_colony_palette.png")
    pal.file_format = "PNG"
    pal.save()
    return pal, emit


def _nodes_on(idb):
    try:
        idb.use_nodes = True
    except Exception:
        pass


def make_materials(pal, emit):
    m = bpy.data.materials.get("LC_mat") or bpy.data.materials.new("LC_mat")
    _nodes_on(m)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = pal; tex.interpolation = "Closest"
    etex = nt.nodes.new("ShaderNodeTexImage"); etex.image = emit; etex.interpolation = "Closest"
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 2.2
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    ecol = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
    nt.links.new(tex.outputs["Color"], bsdf.inputs[ecol])
    nt.links.new(etex.outputs["Color"], mul.inputs[0])
    if "Emission Strength" in bsdf.inputs:
        nt.links.new(mul.outputs[0], bsdf.inputs["Emission Strength"])
    bsdf.inputs["Metallic"].default_value = 0.2
    bsdf.inputs["Roughness"].default_value = 0.4
    nt.links.new(bsdf.outputs[0], out.inputs[0])

    g = bpy.data.materials.get("LC_mannequin") or bpy.data.materials.new("LC_mannequin")
    _nodes_on(g)
    b = g.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (0.55, 0.58, 0.63, 1)
    b.inputs["Roughness"].default_value = 0.6
    return m, g


# ------------------------------------------------------- mesh builder ----
def M(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    return Matrix.Translation(loc) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*scale, 1))


def aim(d):
    """Rotation that points local +Z along direction d."""
    return Vector((0, 0, 1)).rotation_difference(Vector(d).normalized()).to_matrix().to_4x4()


class Builder:
    def __init__(self):
        self.bm = bmesh.new()
        self.sw = self.bm.faces.layers.int.new("sw")
        self.sm = self.bm.faces.layers.int.new("sm")

    def _tag(self, n0, sw, smooth):
        # bmesh reuses freed face slots (e.g. pointed cones), so index ranges are
        # unreliable; use the per-face tag flag to find faces that are new.
        for f in self.bm.faces:
            if not f.tag:
                f[self.sw] = sw
                f[self.sm] = 1 if smooth else 0
                f.tag = True

    def box(self, m, sw):
        n0 = len(self.bm.faces); bmesh.ops.create_cube(self.bm, size=1.0, matrix=m); self._tag(n0, sw, False)

    def sphere(self, r, m, sw, u=24, v=12, smooth=True):
        n0 = len(self.bm.faces)
        bmesh.ops.create_uvsphere(self.bm, u_segments=u, v_segments=v, radius=r, matrix=m)
        self._tag(n0, sw, smooth)

    def ico(self, r, m, sw, sub=1, smooth=False):
        n0 = len(self.bm.faces)
        bmesh.ops.create_icosphere(self.bm, subdivisions=sub, radius=r, matrix=m)
        self._tag(n0, sw, smooth)

    def cone(self, r1, r2, depth, m, sw, seg=16, smooth=False):
        n0 = len(self.bm.faces)
        bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=seg,
                              radius1=r1, radius2=r2, depth=depth, matrix=m)
        self._tag(n0, sw, smooth)

    def torus(self, R, r, m, sw, seg=32, rseg=8, a0=0.0, a1=2 * math.pi, rz=None, phase=0.0, smooth=True):
        rz = r if rz is None else rz
        closed = abs((a1 - a0) - 2 * math.pi) < 1e-6
        rings = seg if closed else seg + 1
        vs = []
        for i in range(rings):
            a = a0 + (a1 - a0) * i / seg
            ring = []
            for j in range(rseg):
                b = 2 * math.pi * j / rseg + phase
                x = (R + r * math.cos(b)) * math.cos(a)
                y = (R + r * math.cos(b)) * math.sin(a)
                z = rz * math.sin(b)
                ring.append(self.bm.verts.new(m @ Vector((x, y, z))))
            vs.append(ring)
        n0 = len(self.bm.faces)
        for i in range(seg):
            i2 = (i + 1) % rings
            for j in range(rseg):
                j2 = (j + 1) % rseg
                self.bm.faces.new((vs[i][j], vs[i2][j], vs[i2][j2], vs[i][j2]))
        if not closed:
            self.bm.faces.new(list(reversed(vs[0])))
            self.bm.faces.new(vs[-1])
        self._tag(n0, sw, smooth)

    def shard(self, root, direction, length, width, thick, sw, crack=None):
        """Crystal shard: 4-sided cone from root, tapering along direction."""
        d = Vector(direction).normalized()
        centre = Vector(root) + d * (length / 2)
        m = Matrix.Translation(centre) @ aim(d) @ Matrix.Diagonal((1, thick / width, 1, 1)) @ Euler((0, 0, math.pi / 4)).to_matrix().to_4x4()
        self.cone(width, 0.0, length, m, sw, seg=4)
        if crack is not None:  # glowing energy crack poking through both faces
            mc = Matrix.Translation(Vector(root) + d * (length * 0.42)) @ aim(d) @ Matrix.Diagonal((width * 0.16, thick * 0.62, length * 0.62, 1))
            self.box(mc, crack)

    def finish(self, name, mat, coll, loc=(0, 0, 0)):
        bm = self.bm
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        uv = bm.loops.layers.uv.new("UVMap")
        off = 0.18 / GRID
        for f in bm.faces:
            i = f[self.sw]
            cu, cv = (i % GRID + 0.5) / GRID, (i // GRID + 0.5) / GRID
            for k, lp in enumerate(f.loops):
                lp[uv].uv = (cu + off * math.cos(k * 2.09), cv + off * math.sin(k * 2.09))
        smooth = [f[self.sm] for f in bm.faces]
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for p, s in zip(me.polygons, smooth):
            p.use_smooth = bool(s)
        ob = bpy.data.objects.new(name, me)
        ob.data.materials.append(mat)
        coll.objects.link(ob)
        ob.location = loc
        return ob


R = math.radians


# ============================================================ ITEMS ======
# Each builder returns a Builder in the item's LOCAL space (origin = its
# attachment point on the reference avatar).

def build_crown():
    """Cosmic Dominion Crown (Hat). Origin = head centre."""
    b = Builder()
    z0 = 0.52
    b.torus(0.62, 0.07, M((0, 0, z0)), 6, seg=32, rseg=8, rz=0.15)            # jeweled band
    b.torus(0.645, 0.03, M((0, 0, z0 - 0.15)), 6, seg=32, rseg=6)            # lower trim
    for k in range(6):                                                         # gems
        a = R(-90 + k * 60)
        b.ico(0.06, M((0.69 * math.cos(a), 0.69 * math.sin(a), z0)), 3 if k % 2 == 0 else 16)
    for k in range(8):                                                         # crystal spires
        a = R(-90 + k * 45)
        h = 0.62 if k % 2 == 0 else 0.42
        if k == 0:
            h = 0.78
        base = Vector((0.6 * math.cos(a), 0.6 * math.sin(a), z0 + 0.1))
        out = Vector((math.cos(a), math.sin(a), 0)) * 0.22 + Vector((0, 0, 1))
        b.shard(base, out, h, 0.12, 0.12, 14, crack=7)
        tip = base + out.normalized() * h
        b.ico(0.055 if k else 0.08, M(tip + Vector((0, 0, 0.03))), 5)
    b.sphere(0.54, M((0, 0, z0 + 0.06), scale=(1, 1, 0.28)), 4, u=24, v=10)   # galaxy disc
    for arm in range(2):                                                       # spiral of stars
        for i in range(10):
            t = i / 9
            a = arm * math.pi + t * 3.2
            r = 0.06 + t * 0.42
            b.ico(0.022 + 0.012 * (1 - t), M((r * math.cos(a), r * math.sin(a), z0 + 0.2 - t * 0.04)), 7 if i % 3 else 13)
    b.torus(0.86, 0.025, M((0, 0, z0 + 0.42), rot=(R(14), 0, 0)), 11, seg=40, rseg=6)  # halo
    b.torus(1.02, 0.012, M((0, 0, z0 + 0.1), rot=(R(-18), R(8), 0)), 16, seg=48, rseg=4)  # orbit path
    for k, ang in enumerate((20, 140, 250, 320)):                              # asteroids
        a = R(ang)
        p = Matrix.Rotation(R(-18), 4, "X") @ Matrix.Rotation(R(8), 4, "Y") @ Vector((1.02 * math.cos(a), 1.02 * math.sin(a), 0))
        b.ico(0.075, M(p + Vector((0, 0, z0 + 0.1)), rot=(k, k * 0.7, 0), scale=(1.2, 0.9, 0.8)), 17)
    return b


def build_visor():
    """Quantum Hacker Visor (Face front). Origin = head centre."""
    b = Builder()
    a0, a1 = R(-168), R(-12)
    b.torus(0.665, 0.03, M((0, 0, 0.06)), 10, seg=28, rseg=6, a0=a0, a1=a1, rz=0.2)    # frame
    b.torus(0.69, 0.012, M((0, 0, 0.06)), 9, seg=28, rseg=6, a0=R(-160), a1=R(-20), rz=0.15, smooth=False)  # neon lens
    for zz in (0.24, -0.12):                                                              # rims
        b.torus(0.68, 0.025, M((0, 0, zz)), 10, seg=28, rseg=6, a0=a0, a1=a1)
    rows = [(0.15, [(-140, 14), (-118, 18), (-92, 10)]), (0.09, [(-130, 22), (-100, 12), (-75, 16)]),
            (0.03, [(-145, 10), (-120, 26), (-82, 20)]), (-0.03, [(-110, 30), (-70, 12), (-50, 14)])]
    for zz, segs in rows:                                                                   # scrolling code
        for k, (ang, span) in enumerate(segs):
            a = R(ang + span / 2)
            L = 0.69 * R(span)
            b.box(M((0.705 * math.cos(a), 0.705 * math.sin(a), zz), rot=(0, 0, a + math.pi / 2), scale=(L, 0.012, 0.022)),
                  13 if k == 0 else 3)
    for s in (-1, 1):                                                                       # earpieces
        x = s * 0.66
        b.cone(0.13, 0.13, 0.1, M((x, -0.06, 0.06), rot=(0, R(90), 0)), 17, seg=16)
        b.cone(0.075, 0.075, 0.12, M((x + s * 0.01, -0.06, 0.06), rot=(0, R(90), 0)), 9, seg=12)
    b.cone(0.012, 0.012, 0.45, M((0.7, -0.06, 0.38)), 17, seg=6)                           # antenna
    b.ico(0.04, M((0.7, -0.06, 0.62)), 9)
    # widen so it clears the corners of the blocky avatar head
    bmesh.ops.transform(b.bm, matrix=Matrix.Diagonal((1.13, 1.13, 1.0, 1.0)), verts=b.bm.verts[:])
    return b


def build_helmet():
    """Lunar Habitat Commander Helmet (Hat). Origin = head centre."""
    b = Builder()
    b.sphere(0.86, M((0, 0, 0.06), scale=(1, 1.04, 1)), 0, u=32, v=16)                    # shell
    # visor: front window of a slightly larger sphere
    vb = Builder()
    vb.sphere(0.885, M((0, 0, 0.06), scale=(1, 1.04, 1)), 1, u=32, v=16)
    kill = [f for f in vb.bm.faces if not (f.calc_center_median().y < -0.28 and abs(f.calc_center_median().x) < 0.6
                                           and -0.36 < f.calc_center_median().z < 0.42)]
    bmesh.ops.delete(vb.bm, geom=kill, context="FACES")
    vb.bm.faces.ensure_lookup_table()
    for f in vb.bm.faces:
        f[vb.sw] = 1; f[vb.sm] = 1
    tmp = bpy.data.meshes.new("tmp_visor"); vb.bm.to_mesh(tmp); vb.bm.free()
    n0 = len(b.bm.faces); b.bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    b._tag(n0, 1, True)
    b.box(M((0, -0.905, 0.25), rot=(R(-12), 0, 0), scale=(0.52, 0.02, 0.035)), 3)          # HUD bar
    b.box(M((-0.18, -0.915, 0.15), rot=(R(-8), 0, 0), scale=(0.16, 0.02, 0.02)), 3)
    b.torus(0.07, 0.012, M((0.22, -0.93, 0.08), rot=(R(90), 0, 0)), 3, seg=16, rseg=4)     # reticle
    b.torus(0.9, 0.04, M((0, 0, 0.46)), 2, seg=24, rseg=6, a0=R(-150), a1=R(-30))          # brow ridge
    b.box(M((0, 0.05, 0.9), rot=(R(-6), 0, 0), scale=(0.1, 0.95, 0.09)), 0)                # fin
    b.box(M((0, 0.05, 0.95), rot=(R(-6), 0, 0), scale=(0.04, 0.9, 0.04)), 3)               # glow strip
    for s in (-1, 1):                                                                       # ear modules
        b.cone(0.21, 0.19, 0.16, M((s * 0.86, 0, 0.02), rot=(0, R(90), 0)), 2, seg=20)
        b.torus(0.13, 0.022, M((s * 0.945, 0, 0.02), rot=(0, R(90), 0)), 3, seg=20, rseg=6)
    b.cone(0.015, 0.015, 0.55, M((-0.9, 0.08, 0.42)), 2, seg=6)                            # antenna
    b.ico(0.045, M((-0.9, 0.08, 0.72)), 3)
    b.torus(0.6, 0.08, M((0, 0, -0.74)), 1, seg=32, rseg=8)                                # collar
    b.torus(0.61, 0.022, M((0, 0, -0.65)), 3, seg=32, rseg=6)
    b.cone(0.11, 0.11, 0.025, M((0, -0.62, 0.66), rot=(R(-52), 0, R(30))), 1, seg=6)        # hex emblem
    b.ico(0.05, M((0, -0.63, 0.675)), 3)
    return b


def build_void_pet():
    """Void Core Shoulder Pet (Shoulder). Origin = where it sits on the shoulder."""
    b = Builder()
    c = Vector((0, 0, 0.38))
    b.sphere(0.32, M(c, scale=(1, 0.95, 1.05)), 12, u=24, v=12)                          # body
    b.torus(0.42, 0.028, M(c, rot=(R(18), R(-10), 0)), 11, seg=32, rseg=6)               # event horizon
    b.torus(0.54, 0.08, M(c, rot=(R(18), R(-10), 0)), 16, seg=32, rseg=6, rz=0.012, smooth=False)  # accretion disk
    for s in (-1, 1):
        b.sphere(0.075, M(c + Vector((s * 0.11, -0.25, 0.08))), 13, u=12, v=8)            # eyes
        b.sphere(0.038, M(c + Vector((s * 0.11, -0.315, 0.08))), 3, u=10, v=6)            # pupils
        b.cone(0.07, 0.0, 0.2, Matrix.Translation(c + Vector((s * 0.16, 0, 0.36))) @ aim((s * 0.45, 0, 1)), 12, seg=6)  # horns
        b.ico(0.035, M(c + Vector((s * 0.205, 0, 0.47))), 11)
        b.sphere(0.07, M((s * 0.12, -0.05, 0.07), scale=(1, 1.3, 0.6)), 14, u=10, v=6)    # feet
    for k in range(7):                                                                    # particles
        a = R(k * 51 + 10)
        b.ico(0.028, M(c + Vector((0.62 * math.cos(a), 0.62 * math.sin(a), 0.08 * math.sin(3 * a) + 0.12))), 11 if k % 2 else 16)
    return b


def build_wings():
    """Singularity Wings (Back). Origin = back attachment (centre of torso back)."""
    b = Builder()
    b.box(M((0, 0.06, 0), scale=(0.55, 0.12, 0.75)), 17)                                   # mount plate
    b.cone(0.26, 0.26, 0.18, M((0, 0.17, 0.08), rot=(R(-90), 0, 0)), 17, seg=20)           # core housing
    b.ico(0.16, M((0, 0.28, 0.08)), 7, sub=2, smooth=True)                                # glowing core
    b.torus(0.23, 0.035, M((0, 0.27, 0.08), rot=(R(90), 0, 0)), 3, seg=24, rseg=6)
    feathers = [(42, 2.3, 0.42), (22, 2.75, 0.4), (2, 2.45, 0.36), (-20, 1.95, 0.3), (-42, 1.4, 0.25)]
    for s in (-1, 1):
        root = Vector((s * 0.24, 0.22, 0.12))
        for k, (ang, L, w) in enumerate(feathers):
            d = Vector((s * math.cos(R(ang)), 0.18, math.sin(R(ang))))
            b.shard(root, d, L, w, w * 0.45, 14 if k % 2 == 0 else 17, crack=7)
            if k < 2:  # secondary branch shard
                mid = root + d.normalized() * (L * 0.45)
                d2 = Vector((s * math.cos(R(ang + 28)), 0.12, math.sin(R(ang + 28))))
                b.shard(mid, d2, L * 0.4, w * 0.6, w * 0.3, 4, crack=3)
    return b


def build_halo():
    """Ancient AI Relic Halo (Hat). Origin = head centre; floats above head."""
    b = Builder()
    z = 1.0
    tilt = M((0, 0, z), rot=(R(10), 0, 0))
    for k in range(8):
        a0 = R(k * 45 + 3.5)
        a1 = a0 + R(38)
        b.torus(0.72, 0.055, tilt, 6 if k % 2 == 0 else 15, seg=6, rseg=4, a0=a0, a1=a1, rz=0.05, phase=R(45), smooth=False)
        g = R(k * 45)                                                                      # glowing nodes in gaps
        b.box(tilt @ M((0.72 * math.cos(g), 0.72 * math.sin(g), 0), rot=(R(45), R(45), g), scale=(0.07, 0.07, 0.07)), 3)
        mid = (a0 + a1) / 2                                                                # circuit nubs
        b.box(tilt @ M((0.72 * math.cos(mid), 0.72 * math.sin(mid), 0.06), rot=(0, 0, mid), scale=(0.025, 0.12, 0.018)), 3)
    b.torus(0.56, 0.014, tilt, 3, seg=40, rseg=4)
    b.torus(0.86, 0.012, tilt, 13, seg=48, rseg=4)
    b.cone(0.09, 0.0, 0.14, tilt @ M((0, 0, 0.12)), 7, seg=4)                               # floating core diamond
    b.cone(0.09, 0.0, 0.1, tilt @ M((0, 0, 0.0), rot=(R(180), 0, 0)), 7, seg=4)
    return b


ITEMS = [
    # key, display name, builder, avatar attach location, roblox accessory type, camera (target, offset, lens)
    ("cosmic_dominion_crown", "Cosmic Dominion Crown", build_crown, (0, 0, 2.6), "Hat",
     ((0, 0, 3.0), (2.4, -4.4, 1.6), 55)),
    ("quantum_hacker_visor", "Quantum Hacker Visor", build_visor, (0, 0, 2.6), "Face Front",
     ((0, 0, 2.65), (2.2, -4.2, 0.9), 60)),
    ("lunar_commander_helmet", "Lunar Habitat Commander Helmet", build_helmet, (0, 0, 2.6), "Hat",
     ((0, 0, 2.7), (2.4, -4.4, 1.0), 55)),
    ("void_core_shoulder_pet", "Void Core Shoulder Pet", build_void_pet, (-1.2, 0, 2.0), "Shoulder",
     ((-1.2, 0, 2.45), (-1.7, -3.3, 0.7), 50)),
    ("singularity_wings", "Singularity Wings", build_wings, (0, 0.5, 1.4), "Back",
     ((0, 0.4, 1.7), (3.2, 6.4, 1.6), 40)),
    ("ai_relic_halo", "Ancient AI Relic Halo", build_halo, (0, 0, 2.6), "Hat",
     ((0, 0, 3.1), (2.2, -4.6, 1.8), 55)),
]


# ----------------------------------------------------------- scene ------
def collection(name):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def clear_collection(c):
    for ob in list(c.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


def mannequin(mat):
    c = collection("LC_Avatar")
    clear_collection(c)
    def part(name, loc, size, bevel=0.08):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0, matrix=M(loc, scale=size))
        bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(name, me); c.objects.link(ob)
        ob.data.materials.append(mat)
        mod = ob.modifiers.new("bevel", "BEVEL"); mod.width = bevel; mod.segments = 4
        for p in me.polygons:
            p.use_smooth = True
        return ob
    part("Torso", (0, 0, 1), (2, 1, 2), 0.06)
    part("Head", (0, 0, 2.6), (1.2, 1.2, 1.2), 0.28)
    part("ArmR", (-1.5, 0, 1), (1, 1, 2), 0.06)
    part("ArmL", (1.5, 0, 1), (1, 1, 2), 0.06)
    part("LegR", (-0.5, 0, -1), (1, 1, 2), 0.06)
    part("LegL", (0.5, 0, -1), (1, 1, 2), 0.06)
    return c


def setup_render(res=(1200, 1200)):
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    ee = sc.eevee
    for attr, val in (("taa_render_samples", 64), ("use_bloom", True), ("bloom_intensity", 0.08), ("use_gtao", True)):
        if hasattr(ee, attr):
            setattr(ee, attr, val)
    world = sc.world or bpy.data.worlds.new("World")
    sc.world = world
    _nodes_on(world)
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.006, 0.009, 0.022, 1)
    bg.inputs[1].default_value = 0.6
    # glare for glow (works on Eevee Next where bloom was removed)
    try:
        if hasattr(sc, "compositing_node_group"):
            nt = bpy.data.node_groups.get("LC_Comp") or bpy.data.node_groups.new("LC_Comp", "CompositorNodeTree")
            sc.compositing_node_group = nt
        else:
            sc.use_nodes = True
            nt = sc.node_tree
        nt.nodes.clear()
        rl = nt.nodes.new("CompositorNodeRLayers")
        gl = nt.nodes.new("CompositorNodeGlare")
        gl.glare_type = "FOG_GLOW"
        if hasattr(gl, "threshold"):
            gl.threshold = 0.9
        if hasattr(gl, "size"):
            gl.size = 7
        if hasattr(sc, "compositing_node_group"):
            comp = nt.nodes.new("NodeGroupOutput")
            if not nt.interface.items_tree:
                nt.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            nt.links.new(rl.outputs["Image"], gl.inputs["Image"])
            nt.links.new(gl.outputs["Image"], comp.inputs[0])
        else:
            comp = nt.nodes.new("CompositorNodeComposite")
            nt.links.new(rl.outputs["Image"], gl.inputs["Image"])
            nt.links.new(gl.outputs["Image"], comp.inputs["Image"])
    except Exception:
        pass
    # lights
    c = collection("LC_Lights")
    clear_collection(c)
    def light(name, kind, loc, energy, color, size=None, rot=None):
        ld = bpy.data.lights.new(name, kind); ld.energy = energy; ld.color = color
        if size and hasattr(ld, "size"):
            ld.size = size
        ob = bpy.data.objects.new(name, ld); c.objects.link(ob); ob.location = loc
        if rot:
            ob.rotation_euler = rot
        return ob
    light("Key", "AREA", (4, -5, 6), 260, (1, 0.97, 0.94), 4, (R(45), 0, R(38)))
    light("Rim", "AREA", (-4, 5, 5), 320, (0.45, 0.75, 1.0), 4, (R(-45), 0, R(-140)))
    light("Fill", "AREA", (-5, -3, 2), 90, (0.8, 0.7, 1.0), 5, (R(70), 0, R(-60)))
    back = light("Back", "AREA", (3, 7, 5), 260, (0.9, 0.9, 1.0), 4)
    back.rotation_euler = (Vector((0, 0, 1.5)) - back.location).to_track_quat("-Z", "Y").to_euler()


def camera(target, offset, lens):
    c = collection("LC_Lights")
    cam = bpy.data.objects.get("LC_Cam")
    if not cam:
        cam = bpy.data.objects.new("LC_Cam", bpy.data.cameras.new("LC_Cam"))
        c.objects.link(cam)
    cam.data.lens = lens
    t = Vector(target)
    cam.location = t + Vector(offset)
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def export(ob, key):
    loc = ob.location.copy()
    ob.location = (0, 0, 0)
    for o in bpy.data.objects:
        try:
            o.select_set(False)
        except Exception:
            pass
    ob.data.name = key
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    fbx = os.path.join(OUT, key + ".fbx")
    glb = os.path.join(OUT, key + ".glb")
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"MESH"},
                             mesh_smooth_type="FACE", path_mode="COPY", embed_textures=True,
                             apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True)
    ob.location = loc
    return fbx, glb


# ------------------------------------------------------------- run ------
def run(mode="build", item=None):
    pal, emit = make_images()
    mat, gray = make_materials(pal, emit)
    out = {"dir": OUT}
    if mode == "build":
        c = collection("LC_UGC")
        clear_collection(c)
        stats = []
        for key, name, fn, attach, kind, _ in ITEMS:
            ob = fn().finish(key, mat, c, attach)
            dims = [round(v, 2) for v in ob.dimensions]
            fbx, glb = export(ob, key)
            stats.append({"key": key, "tris": len(ob.data.polygons), "dims_studs": dims, "type": kind,
                          "fbx": os.path.getsize(fbx), "glb": os.path.getsize(glb)})
        mannequin(gray)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "lunar_colony_ugc.blend"))
        out["items"] = stats
    elif mode == "render":
        setup_render()
        c = collection("LC_UGC")
        for ob in c.objects:
            ob.hide_render = ob.name != item
        for ob in collection("LC_Avatar").objects:
            ob.hide_render = False
        entry = next(i for i in ITEMS if i[0] == item)
        tgt, off, lens = entry[5]
        camera(tgt, off, lens)
        path = os.path.join(OUT, item + "_render.png")
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        out["render"] = path
    elif mode == "lineup":
        setup_render((2400, 1000))
        c = collection("LC_UGC")
        for ob in collection("LC_Avatar").objects:
            ob.hide_render = True
        saved = {ob.name: (ob.location.copy(), ob.scale.copy()) for ob in c.objects}
        layout = {"singularity_wings": (0, 1.5, 3.3, 0.85, 180), "cosmic_dominion_crown": (-5.0, 0, 0.9, 1, -15),
                  "quantum_hacker_visor": (-2.6, 0, 1.4, 1, -15), "lunar_commander_helmet": (0, -0.6, 1.3, 1, -15),
                  "void_core_shoulder_pet": (2.5, 0, 1.0, 1.2, -15), "ai_relic_halo": (4.9, 0, 0.5, 1, -15)}
        for ob in c.objects:
            x, y, z, sc_, rz = layout[ob.name]
            ob.hide_render = False
            ob.location = (x, y, z); ob.scale = (sc_, sc_, sc_); ob.rotation_euler = (0, 0, R(rz))
        camera((0, 0, 1.9), (0, -15, 2.2), 40)
        path = os.path.join(OUT, "ugc_lineup_render.png")
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        for ob in c.objects:
            ob.location, ob.scale = saved[ob.name]
            ob.rotation_euler = (0, 0, 0)
        out["render"] = path
    return out


if __name__ == "__main__":
    run("build")
    for _key, *_ in ITEMS:
        run("render", _key)
    run("lineup")
