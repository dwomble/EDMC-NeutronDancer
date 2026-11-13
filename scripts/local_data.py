"""Build the local routing indexes from Spansh galaxy dumps and package them for the star-data release."""
import argparse, hashlib, json, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from Router.local.index import Index, build, galaxy_extras, occupancy  # noqa: E402

def package(idx:Index, kind:str, out:Path, manifest:dict) -> None:
    """Save an index, zip it up as <kind>.zip and record it in the manifest."""
    folder:Path = out / kind
    idx.save(folder)
    asset:Path = out / f'{kind}.zip'
    with zipfile.ZipFile(asset, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder.iterdir()): z.write(f, arcname=f.name)

    sha = hashlib.sha256()
    with open(asset, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): sha.update(chunk)
    manifest['files'][kind] = {'asset': asset.name, 'sha256': sha.hexdigest(), 'size': asset.stat().st_size, 'stars': len(idx),
                               'built': datetime.now(timezone.utc).strftime('%Y-%m-%d')}
    print(f"{kind}: {len(idx):,} stars, {asset.stat().st_size / 2 ** 20:.0f} MiB", flush=True)

def main() -> None:
    """Run one build mode against a dump, updating out/manifest.json."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=('full', 'addon'))
    ap.add_argument('out', type=Path, help='folder for the packaged indexes and manifest.json')
    ap.add_argument('--galaxy', required=True, help='gzipped Spansh galaxy dump, or - to read it from stdin')
    ap.add_argument('--systems', type=Path, required=True, help='gzipped Spansh systems dump covering the same period')
    ap.add_argument('--base', type=Path, help='folder holding the unpacked neutron and kgbfoam indexes the add-ons extend')
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    path:Path = args.out / 'manifest.json'
    manifest:dict = json.loads(path.read_text()) if path.exists() else {}
    manifest.setdefault('files', {})

    # The systems dump names every system's main star; the galaxy dump adds the star distances behind fuel stops and
    # secondary neutrons, but leaves out the main star of any system whose stars nobody has scanned.
    # full: both indexes from systems.json.gz and galaxy.json.gz, and a fresh base needs no add-ons.
    # addon: neutrons and fuel stars from the 1-month dumps, kept only where the base has none nearby,
    # plus fuel-stop neutrons the base doesn't already have.
    extras:dict = galaxy_extras(sys.stdin.buffer if args.galaxy == '-' else Path(args.galaxy))
    nf, ns = sum(e[0] for e in extras.values()), sum(e[1] for e in extras.values())
    print(f"galaxy: {nf:,} fuel stops, {ns:,} secondary neutrons", flush=True)
    if args.mode == 'full':
        for kind, idx in build(args.systems, extras=extras).items(): package(idx, kind, args.out, manifest)
        for kind in ('neutron_add', 'kgbfoam_add'): manifest['files'].pop(kind, None)
    if args.mode == 'addon':
        if not args.base: ap.error('addon mode needs --base')
        base:dict = {k: Index.load(args.base / k) for k in ('neutron', 'kgbfoam')}
        stops:set = {base['neutron'].id64(i) for i in range(len(base['neutron'])) if base['neutron'].fuel(i)}
        for kind, idx in build(args.systems, seen={k: occupancy(v) for k, v in base.items()}, skip=stops, extras=extras).items():
            package(idx, f'{kind}_add', args.out, manifest)

    path.write_text(json.dumps(manifest, indent=2))

if __name__ == '__main__':
    main()
