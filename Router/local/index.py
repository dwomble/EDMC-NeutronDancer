import gzip, json, math, mmap, sys
from array import array
from bisect import bisect_left, bisect_right
from pathlib import Path

CELL:float = 100.0
SUB:float = 33.34
LO:tuple = (-45000.0, -6000.0, -25000.0)
DIM:tuple = (int(90000 / SUB) + 1, int(12000 / SUB) + 1, int(95000 / SUB) + 1)
KINDS:dict = {'neutron': ('"mainStar":"Neutron Star"',), 'kgbfoam': tuple(f'"mainStar":"{c} (' for c in 'OBAFGKM')}
TYPES:dict = {'xs': 'f', 'ys': 'f', 'zs': 'f', 'ids': 'Q', 'ukeys': 'q', 'starts': 'q', 'offs': 'Q'}
VERSION:int = 2
CHUNK:int = 1 << 26  # bytes read per call when loading, so other threads get the GIL between reads

class Index:
    """
    Generate compact, cell-sorted star indexes from Spansh system dumps.
    """

    @staticmethod
    def _cell(x:float, y:float, z:float) -> tuple:
        """100 Ly grid cell for a coordinate."""
        return (int(x // CELL), int(y // CELL), int(z // CELL))

    @staticmethod
    def _key(cx:int, cy:int, cz:int) -> int:
        """Pack a cell into one int that sorts x, then y, then z."""
        return ((cx + 1024) << 22) | ((cy + 1024) << 11) | (cz + 1024)

    def __init__(self, arrs:dict, blob:bytes|mmap.mmap) -> None:
        # Built indexes hold arrays; loaded ones hold typed views over the bytes read from disk, which index the same way
        self.xs:array|memoryview = arrs['xs']; self.ys:array|memoryview = arrs['ys']; self.zs:array|memoryview = arrs['zs']
        self.ids:array|memoryview = arrs['ids']; self.ukeys:array|memoryview = arrs['ukeys']
        self.starts:array|memoryview = arrs['starts']; self.offs:array|memoryview = arrs['offs']
        self.blob:bytes|mmap.mmap = blob

    def __len__(self) -> int:
        return len(self.xs)

    def pos(self, i:int) -> tuple:
        """Coordinates of star i."""
        return (self.xs[i], self.ys[i], self.zs[i])

    def id64(self, i:int) -> int:
        """System address of star i."""
        return self.ids[i]

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
            with open(folder / f'{k}.bin', 'wb') as f: f.write(getattr(self, k))
        (folder / 'names.bin').write_bytes(self.blob)
        meta:dict = {'version': VERSION, 'stars': len(self), 'cells': len(self.ukeys), 'byteorder': sys.byteorder}
        (folder / 'meta.json').write_text(json.dumps(meta))

    @classmethod
    def load(cls, folder:Path) -> 'Index':
        """Read an index written by save()."""
        meta:dict = json.loads((folder / 'meta.json').read_text())
        if meta.get('version') != VERSION: raise ValueError(f'unsupported index version {meta.get("version")}')

        # Reading in chunks straight into place releases the GIL between reads and never copies the data again,
        # so the UI keeps drawing while gigabytes load on a worker thread. Anonymous memory is zeroed lazily by the OS,
        # where a bytearray would zero every byte up front while holding the GIL.
        def read(path:Path) -> mmap.mmap:
            buf:mmap.mmap = mmap.mmap(-1, max(path.stat().st_size, 1))
            view:memoryview = memoryview(buf)
            with open(path, 'rb', buffering=0) as f:
                got:int = 0
                while got < len(buf) and (n := f.readinto(view[got:got + CHUNK])): got += n
            return buf

        arrs:dict = {}
        for k, t in TYPES.items():
            buf:mmap.mmap = read(folder / f'{k}.bin')
            if meta.get('byteorder') == sys.byteorder:
                arrs[k] = memoryview(buf).cast(t)
                continue

            # A file from a machine of the other byte order needs swapping, which a view can't do in place
            arrs[k] = array(t, buf)
            arrs[k].byteswap()
        return cls(arrs, read(folder / 'names.bin'))

def _bit(x:float, y:float, z:float) -> int|None:
    """Sub-cube bit for a coordinate, or None outside the fixed galactic box."""
    i, j, k = int((x - LO[0]) // SUB), int((y - LO[1]) // SUB), int((z - LO[2]) // SUB)
    return (i * DIM[1] + j) * DIM[2] + k if 0 <= i < DIM[0] and 0 <= j < DIM[1] and 0 <= k < DIM[2] else None

def occupancy(idx:Index) -> bytearray:
    """Sub-cube bits already holding a star of this index, so an add-on only keeps stars in empty sub-cubes."""
    seen:bytearray = bytearray(DIM[0] * DIM[1] * DIM[2] // 8 + 1)
    for n in range(len(idx)):
        bit:int|None = _bit(idx.xs[n], idx.ys[n], idx.zs[n])
        if bit is not None: seen[bit >> 3] |= 1 << (bit & 7)
    return seen

def build(src:Path, kinds:tuple = ('neutron', 'kgbfoam'), seen:dict|None = None) -> dict:
    """One pass over a gzipped dump, keeping the first star of each kind per sub-cube not already in seen."""

    # Collect each kind in arrival order first; sorting by cell needs every star, so it happens after the pass.
    # Names go into one byte blob with an offset per star, since millions of Python strings would cost gigabytes.
    cols:dict = {k: {'xs': array('f'), 'ys': array('f'), 'zs': array('f'), 'ids': array('Q'), 'keys': array('q'),
                     'offs': array('Q', [0]), 'blob': bytearray(),
                     'seen': (seen or {}).get(k) or bytearray(DIM[0] * DIM[1] * DIM[2] // 8 + 1)} for k in kinds}

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
            bit:int|None = _bit(x, y, z)
            if bit is not None:
                if c['seen'][bit >> 3] & (1 << (bit & 7)): continue
                c['seen'][bit >> 3] |= 1 << (bit & 7)

            c['xs'].append(x); c['ys'].append(y); c['zs'].append(z); c['ids'].append(r['id64'])
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
        arrs:dict = {'xs': array('f'), 'ys': array('f'), 'zs': array('f'), 'ids': array('Q'), 'ukeys': array('q'),
                     'starts': array('q'), 'offs': array('Q', [0])}
        blob:bytearray = bytearray()

        for n, o in enumerate(order):
            # Each new cell key records where that cell's run of stars starts, which near() uses to find them
            if not arrs['ukeys'] or arrs['ukeys'][-1] != keys[o]:
                arrs['ukeys'].append(keys[o]); arrs['starts'].append(n)
            arrs['xs'].append(c['xs'][o]); arrs['ys'].append(c['ys'][o]); arrs['zs'].append(c['zs'][o]); arrs['ids'].append(c['ids'][o])
            blob += c['blob'][c['offs'][o]:c['offs'][o + 1]]
            arrs['offs'].append(len(blob))

        # A closing start lets the last cell's run end at starts[j + 1] like every other cell
        arrs['starts'].append(len(order))
        out[kind] = Index(arrs, bytes(blob))
    return out

class Combined:
    """A base index and its add-on searched as one, with the add-on's stars numbered after the base's."""

    def __init__(self, base:Index, add:Index) -> None:
        self.base:Index = base
        self.add:Index = add
        self.split:int = len(base)

    def __len__(self) -> int:
        return self.split + len(self.add)

    def pos(self, i:int) -> tuple:
        return self.base.pos(i) if i < self.split else self.add.pos(i - self.split)

    def name(self, i:int) -> str:
        return self.base.name(i) if i < self.split else self.add.name(i - self.split)

    def id64(self, i:int) -> int:
        return self.base.id64(i) if i < self.split else self.add.id64(i - self.split)

    def near(self, p:tuple, rad:float) -> list:
        return self.base.near(p, rad) + [(i + self.split, d) for i, d in self.add.near(p, rad)]
