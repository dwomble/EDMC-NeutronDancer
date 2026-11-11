"""Compact, cell-sorted star indexes built from Spansh system dumps."""
import gzip, json, math, sys
from array import array
from bisect import bisect_left, bisect_right
from pathlib import Path

CELL:float = 100.0
SUB:float = 33.34
LO:tuple = (-45000.0, -6000.0, -25000.0)
DIM:tuple = (int(90000 / SUB) + 1, int(12000 / SUB) + 1, int(95000 / SUB) + 1)
KINDS:dict = {'neutron': ('"mainStar":"Neutron Star"',), 'kgbfoam': tuple(f'"mainStar":"{c} (' for c in 'OBAFGKM')}
TYPES:dict = {'xs': 'f', 'ys': 'f', 'zs': 'f', 'ukeys': 'q', 'starts': 'q', 'offs': 'Q'}
VERSION:int = 1

class Index:
    """Stars sorted by grid cell, as flat coordinate arrays plus a name blob."""

    @staticmethod
    def _cell(x:float, y:float, z:float) -> tuple:
        """100 Ly grid cell for a coordinate."""
        return (int(x // CELL), int(y // CELL), int(z // CELL))

    @staticmethod
    def _key(cx:int, cy:int, cz:int) -> int:
        """Pack a cell into one int that sorts x, then y, then z."""
        return ((cx + 1024) << 22) | ((cy + 1024) << 11) | (cz + 1024)

    def __init__(self, arrs:dict, blob:bytes) -> None:
        self.xs:array = arrs['xs']; self.ys:array = arrs['ys']; self.zs:array = arrs['zs']
        self.ukeys:array = arrs['ukeys']; self.starts:array = arrs['starts']; self.offs:array = arrs['offs']
        self.blob:bytes = blob

    def __len__(self) -> int:
        return len(self.xs)

    def pos(self, i:int) -> tuple:
        """Coordinates of star i."""
        return (self.xs[i], self.ys[i], self.zs[i])

    def name(self, i:int) -> str:
        """System name of star i."""
        return self.blob[self.offs[i]:self.offs[i + 1]].decode('utf-8')

    def near(self, p:tuple, rad:float) -> list:
        """(index, distance) for every star within rad of p."""
        cx0, cy0, cz0 = self._cell(p[0] - rad, p[1] - rad, p[2] - rad)
        cx1, cy1, cz1 = self._cell(p[0] + rad, p[1] + rad, p[2] + rad)
        xs, ys, zs, r2 = self.xs, self.ys, self.zs, rad * rad
        out:list = []

        # Cells sort x, y, z, so each (x, y) column is one contiguous run: two bisects instead of one per cell
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                j0:int = bisect_left(self.ukeys, self._key(cx, cy, cz0))
                j1:int = bisect_right(self.ukeys, self._key(cx, cy, cz1))
                for i in range(self.starts[j0], self.starts[j1]) if j0 < j1 else ():
                    dx, dy, dz = xs[i] - p[0], ys[i] - p[1], zs[i] - p[2]
                    s:float = dx * dx + dy * dy + dz * dz
                    if s <= r2: out.append((i, math.sqrt(s)))
        return out

    def save(self, folder:Path) -> None:
        """Write the arrays and names as raw files plus a small header."""
        folder.mkdir(parents=True, exist_ok=True)
        for k in TYPES:
            with open(folder / f'{k}.bin', 'wb') as f: getattr(self, k).tofile(f)
        (folder / 'names.bin').write_bytes(self.blob)
        meta:dict = {'version': VERSION, 'stars': len(self), 'cells': len(self.ukeys), 'byteorder': sys.byteorder}
        (folder / 'meta.json').write_text(json.dumps(meta))

    @classmethod
    def load(cls, folder:Path) -> 'Index':
        """Read an index written by save()."""
        meta:dict = json.loads((folder / 'meta.json').read_text())
        if meta.get('version') != VERSION: raise ValueError(f'unsupported index version {meta.get("version")}')

        arrs:dict = {}
        for k, t in TYPES.items():
            arrs[k] = array(t)
            arrs[k].frombytes((folder / f'{k}.bin').read_bytes())
            if meta.get('byteorder') != sys.byteorder: arrs[k].byteswap()
        return cls(arrs, (folder / 'names.bin').read_bytes())

def build(src:Path, kinds:tuple = ('neutron', 'kgbfoam')) -> dict:
    """One pass over a gzipped dump, keeping the first star of each kind per sub-cube."""

    # Collect each kind in arrival order first; sorting by cell needs every star, so it happens after the pass.
    # Names go into one byte blob with an offset per star, since millions of Python strings would cost gigabytes.
    cols:dict = {k: {'xs': array('f'), 'ys': array('f'), 'zs': array('f'), 'keys': array('q'),
                     'offs': array('Q', [0]), 'blob': bytearray(),
                     'seen': bytearray(DIM[0] * DIM[1] * DIM[2] // 8 + 1)} for k in kinds}

    with gzip.open(src, 'rt', encoding='utf-8') as f:
        for line in f:
            # Spansh writes one compact system per line, so a substring test skips most rows without parsing JSON
            kind:str|None = next((k for k in kinds if any(m in line for m in KINDS[k])), None)
            if kind is None: continue

            # Lines carry the array's trailing comma, which json.loads won't accept
            r:dict = json.loads(line.strip().rstrip(','))
            x, y, z = r['coords']['x'], r['coords']['y'], r['coords']['z']
            c:dict = cols[kind]

            # Thin dense regions: one bit per sub-cube records whether this kind already has a star there.
            # A bit array over a fixed box costs about 330 MB; a set of tens of millions of cube tuples would not fit.
            # Stars outside the box (bad coordinates, far outliers) are always kept rather than tracked.
            i, j, k = int((x - LO[0]) // SUB), int((y - LO[1]) // SUB), int((z - LO[2]) // SUB)
            if 0 <= i < DIM[0] and 0 <= j < DIM[1] and 0 <= k < DIM[2]:
                bit:int = (i * DIM[1] + j) * DIM[2] + k
                if c['seen'][bit >> 3] & (1 << (bit & 7)): continue
                c['seen'][bit >> 3] |= 1 << (bit & 7)

            c['xs'].append(x); c['ys'].append(y); c['zs'].append(z)
            c['keys'].append(Index._key(*Index._cell(x, y, z)))
            c['blob'] += r['name'].encode('utf-8')
            c['offs'].append(len(c['blob']))

    out:dict = {}
    for kind, c in cols.items():
        # The sub-cube bits are only needed during the pass; free them before sorting doubles the arrays
        del c['seen']

        # Sort star positions by cell key, then copy every array into that order
        keys:array = c['keys']
        order:list = sorted(range(len(keys)), key=keys.__getitem__)
        arrs:dict = {'xs': array('f'), 'ys': array('f'), 'zs': array('f'), 'ukeys': array('q'), 'starts': array('q'),
                     'offs': array('Q', [0])}
        blob:bytearray = bytearray()

        for n, o in enumerate(order):
            # Each new cell key records where that cell's run of stars starts, which near() uses to find them
            if not arrs['ukeys'] or arrs['ukeys'][-1] != keys[o]:
                arrs['ukeys'].append(keys[o]); arrs['starts'].append(n)
            arrs['xs'].append(c['xs'][o]); arrs['ys'].append(c['ys'][o]); arrs['zs'].append(c['zs'][o])
            blob += c['blob'][c['offs'][o]:c['offs'][o + 1]]
            arrs['offs'].append(len(blob))

        # A closing start lets the last cell's run end at starts[j + 1] like every other cell
        arrs['starts'].append(len(order))
        out[kind] = Index(arrs, bytes(blob))
    return out
