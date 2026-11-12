"""Build the local routing indexes from Spansh dumps and package them for the star-data release."""
import argparse, hashlib, json, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from Router.local.index import Index, build, occupancy  # noqa: E402

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
    ap.add_argument('mode', choices=('full', 'neutron', 'addon'))
    ap.add_argument('dump', type=Path, help='gzipped Spansh systems dump')
    ap.add_argument('out', type=Path, help='folder for the packaged indexes and manifest.json')
    ap.add_argument('--base', type=Path, help='unpacked kgbfoam index the add-on extends (addon mode)')
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    path:Path = args.out / 'manifest.json'
    manifest:dict = json.loads(path.read_text()) if path.exists() else {}
    manifest.setdefault('files', {})

    # full: both indexes from systems.json.gz, and a fresh base needs no add-on.
    # neutron: the neutron index alone from the much smaller systems_neutron.json.gz.
    # addon: fuel stars from a recent delta dump, kept only where the base has none nearby.
    if args.mode == 'full':
        for kind, idx in build(args.dump).items(): package(idx, kind, args.out, manifest)
        manifest['files'].pop('kgbfoam_add', None)
    if args.mode == 'neutron':
        package(build(args.dump, ('neutron',))['neutron'], 'neutron', args.out, manifest)
    if args.mode == 'addon':
        if not args.base: ap.error('addon mode needs --base')
        seen:dict = {'kgbfoam': occupancy(Index.load(args.base))}
        package(build(args.dump, ('kgbfoam',), seen)['kgbfoam'], 'kgbfoam_add', args.out, manifest)

    path.write_text(json.dumps(manifest, indent=2))

if __name__ == '__main__':
    main()
