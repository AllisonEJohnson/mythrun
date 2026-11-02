#!/usr/bin/env python3
"""Bake the Dungeon art pieces Mythrun uses into index.html.

The ithappy Dungeon pack is licensed art kept in the private madison-game-art
repository. Its raw files must not be published, so this script reads only the
pieces listed in PIECES, turns each one into compact game data (quantised
positions, one palette colour per vertex, triangle indices) and writes that into
the <script id="dungeon-art"> block of index.html. No pack files are copied.

    python3 tools/pack_dungeon_art.py --art ../madison-game-art/Dungeon

Requires Pillow (pip install pillow).
"""
import argparse, base64, glob, json, os, re, struct, sys

from PIL import Image

# name -> options. clip=(ymin, ymax) keeps only triangles whose centre height is in range.
PIECES = {
    # structure
    'tunnel_005': {}, 'tunnel_031': {},                              # 4 m wall panels (rough stone, brick)
    'tunnel_037': {},                                                # plain 4 m floor (tops of walls)
    'tunnel_044': {},                                                # ritual circle floor
    'tunnel_013': {},                                                # floor drain
    'tunnel_039': {},                                                # fire grate floor
    'tunnel_arch_002': {},                                           # the great gate's arch
    'tunnel_033': {},                                                # portcullis
    'decoration_028': {},                                            # square stone pillar
    'decoration_031': {},                                            # wooden beam
    # lights
    'light_002': {}, 'light_006': {}, 'light_017': {},
    # statues and set pieces
    'decoration_014': {}, 'decoration_017': {}, 'decoration_026': {}, 'decoration_021': {},
    # hazards
    'torture_013': {}, 'torture_007': {},
    # torture chamber
    'torture_003': {}, 'torture_004': {}, 'torture_006': {}, 'torture_009': {},
    # graves and crypt
    'grave_035': {}, 'grave_018': {}, 'grave_019': {}, 'grave_020': {},
    'grave_007': {}, 'grave_013': {}, 'grave_029': {}, 'grave_034': {},
    'coffin_003': {}, 'coffin_005': {}, 'coffin_001': {},
    # bones
    'bones_024': {}, 'bones_025': {}, 'bones_008': {}, 'bones_002': {}, 'bones_028': {},
    # storage, furniture and banners
    'barrel_002': {}, 'library_003': {}, 'table_002': {}, 'table_prop_001': {}, 'chair_003': {},
    'prop_010': {}, 'prop_058': {}, 'prop_057': {}, 'prop_017': {},
    'prop_013': {}, 'prop_018': {}, 'prop_056': {},
    # rubble
    'stone_009': {}, 'tile_001': {},
}

GRID = 11  # the palette texture is an 11 x 11 grid of flat colours


def read_glb(path):
    b = open(path, 'rb').read()
    magic, ver, length = struct.unpack('<III', b[:12])
    assert magic == 0x46546C67, path
    off = 12; js = None; bin_ = None
    while off < length:
        cl, ct = struct.unpack('<II', b[off:off + 8]); chunk = b[off + 8:off + 8 + cl]
        if ct == 0x4E4F534A: js = json.loads(chunk)
        elif ct == 0x004E4942: bin_ = chunk
        off += 8 + cl
    return js, bin_


def accessor(js, bin_, i):
    a = js['accessors'][i]; bv = js['bufferViews'][a['bufferView']]
    n = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[a['type']]
    fmt = {5126: 'f', 5123: 'H', 5125: 'I', 5121: 'B'}[a['componentType']]
    size = struct.calcsize(fmt)
    stride = bv.get('byteStride') or size * n
    base = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    out = []
    for k in range(a['count']):
        o = base + k * stride
        out.append(struct.unpack('<' + fmt * n, bin_[o:o + size * n]))
    return out


def mat4_apply(m, p):
    x, y, z = p
    return (m[0] * x + m[4] * y + m[8] * z + m[12], m[1] * x + m[5] * y + m[9] * z + m[13], m[2] * x + m[6] * y + m[10] * z + m[14])


def palette(img_path):
    im = Image.open(img_path).convert('RGB'); w, h = im.size
    pal = []
    for r in range(GRID):
        for c in range(GRID):
            pal.append(im.getpixel((int((c + 0.5) * w / GRID), int((r + 0.5) * h / GRID))))
    return im, pal


_NEAR = {}


def nearest(pal, rgb):
    if rgb in _NEAR: return _NEAR[rgb]
    _NEAR[rgb] = min(range(len(pal)), key=lambda i: sum((pal[i][k] - rgb[k]) ** 2 for k in range(3)))
    return _NEAR[rgb]


def convert(path, opts, im, pal):
    js, bin_ = read_glb(path)
    w, h = im.size
    parts = {'s': ([], [], {}), 'g': ([], [], {})}  # verts, indices, dedupe map
    for node in js['nodes']:
        if 'mesh' not in node: continue
        m = node.get('matrix')
        for pr in js['meshes'][node['mesh']]['primitives']:
            pos = accessor(js, bin_, pr['attributes']['POSITION'])
            uv = accessor(js, bin_, pr['attributes']['TEXCOORD_0'])
            idx = [i[0] for i in accessor(js, bin_, pr['indices'])]
            if m: pos = [mat4_apply(m, p) for p in pos]
            glow = js['materials'][pr.get('material', 0)]['name'].startswith('Emissive')
            verts, inds, seen = parts['g' if glow else 's']
            for t in range(0, len(idx), 3):
                tri = idx[t:t + 3]
                cy = sum(pos[i][1] for i in tri) / 3
                if 'clip' in opts and not (opts['clip'][0] <= cy <= opts['clip'][1]): continue
                u = sum(uv[i][0] for i in tri) / 3 % 1.0; v = sum(uv[i][1] for i in tri) / 3 % 1.0
                col = nearest(pal, im.getpixel((min(w - 1, int(u * w)), min(h - 1, int(v * h)))))
                for i in tri:
                    key = (round(pos[i][0], 4), round(pos[i][1], 4), round(pos[i][2], 4), col)
                    if key not in seen:
                        seen[key] = len(verts); verts.append((pos[i], col))
                    inds.append(seen[key])
    return parts


def pack(art):
    im, pal = palette(os.path.join(art, 'Textures', 'Demonstration_Textures.png'))
    files = {os.path.basename(p)[:-4]: p for p in glob.glob(os.path.join(art, 'Meshes', 'assets', '**', '*.glb'), recursive=True)}
    header = {'pal': [list(c) for c in pal], 'order': [], 'pieces': {}}
    data = bytearray()
    def align():
        while len(data) % 4: data.append(0)
    for name, opts in PIECES.items():
        parts = convert(files[name], opts, im, pal)
        allp = [p for k in 'sg' for p, _ in parts[k][0]]
        lo = [min(p[a] for p in allp) for a in range(3)]; hi = [max(p[a] for p in allp) for a in range(3)]
        key = opts.get('as', name)
        entry = {'min': [round(x, 5) for x in lo], 'max': [round(x, 5) for x in hi]}
        for k in 'sg':
            verts, inds, _ = parts[k]
            if not inds: continue
            assert len(verts) < 65536, name
            entry[k] = [len(verts), len(inds)]
            for p, _ in verts:
                for a in range(3):
                    ext = (hi[a] - lo[a]) or 1.0
                    data += struct.pack('<h', round((p[a] - lo[a]) / ext * 65535) - 32768)
            align()
            for _, c in verts: data.append(c)
            align()
            for i in inds: data += struct.pack('<H', i)
            align()
        header['order'].append(key); header['pieces'][key] = entry
    hj = json.dumps(header, separators=(',', ':')).encode()
    blob = struct.pack('<I', len(hj)) + hj
    while len(blob) % 4: blob += b'\0'
    return blob + bytes(data), header


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--art', required=True, help='path to madison-game-art/Dungeon')
    ap.add_argument('--html', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'index.html'))
    a = ap.parse_args()
    blob, header = pack(a.art)
    b64 = base64.b64encode(blob).decode()
    lines = '\n'.join(b64[i:i + 120] for i in range(0, len(b64), 120))
    html = open(a.html, encoding='utf-8').read()
    pat = re.compile(r'(<script id="dungeon-art" type="application/octet-stream">)(.*?)(</script>)', re.S)
    if not pat.search(html): sys.exit('index.html has no <script id="dungeon-art"> block')
    html = pat.sub(lambda m: m.group(1) + '\n' + lines + '\n' + m.group(3), html)
    open(a.html, 'w', encoding='utf-8').write(html)
    tv = sum(e.get('s', [0])[0] + e.get('g', [0])[0] for e in header['pieces'].values())
    print(f'{len(header["order"])} pieces, {tv} vertices, {len(blob)} bytes, {len(b64)} base64 chars')


if __name__ == '__main__':
    main()
