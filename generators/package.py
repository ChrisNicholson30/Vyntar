#!/usr/bin/env python3
"""Refresh bundle manifest, or build an offline versioned release archive."""
import argparse
import hashlib
import io
import tarfile
from pathlib import Path
from theme_core import ROOT

ap=argparse.ArgumentParser(); ap.add_argument('--archive',action='store_true'); args=ap.parse_args()
names=['VERSION','LICENSE','README.md','CHANGELOG.md','install.sh','update.sh','uninstall.sh','bin/vyntar','scripts/lib/runtime.sh','scripts/lib/palette-preview.sh','palette/palette.json']
names += [p.relative_to(ROOT).as_posix() for directory in ['themes','docs','assets/previews','tests/fixtures'] for p in sorted((ROOT/directory).rglob('*')) if p.is_file()]
for name in names:
    if not (ROOT/name).is_file(): raise SystemExit('Missing asset: '+name)
manifest=''.join(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in names)
(ROOT/'MANIFEST.sha256').write_text(manifest)
print('Manifest: %d payloads'%len(names))
if args.archive:
    version=(ROOT/'VERSION').read_text().strip(); prefix='vyntar-'+version
    out=ROOT/'dist'/ (prefix+'.tar.gz'); out.parent.mkdir(exist_ok=True)
    # Canonical owner, timestamps and gzip mtime for reproducibility.
    import gzip
    with out.open('wb') as raw, gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as gz, tarfile.open(fileobj=gz,mode='w') as tar:
        for name in sorted(names+['MANIFEST.sha256']):
            path=ROOT/name; data=path.read_bytes(); info=tarfile.TarInfo(prefix+'/'+name)
            info.size=len(data); info.mode=0o755 if name in ['install.sh','update.sh','uninstall.sh','bin/vyntar'] else 0o644
            info.mtime=0; tar.addfile(info,io.BytesIO(data))
    digest=hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix(out.suffix+'.sha256').write_text(digest+'  '+out.name+'\n')
    print(out)
