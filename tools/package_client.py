#!/usr/bin/env python3
"""Zip a game client folder for the account manager's download list.

    python3 tools/package_client.py /path/to/ZATHROTH downloads/ZATHROTH-client.zip

The zip holds one top-level folder, named after the client folder, so players
extract it and run bin/client.exe. A .sha256 file is written next to it.
"""

import hashlib
from pathlib import Path
import sys
import zipfile


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    folder, target = Path(sys.argv[1]), Path(sys.argv[2])
    if not (folder / "bin").is_dir():
        raise SystemExit(f"{folder} does not look like a client folder (no bin/)")
    target.parent.mkdir(parents=True, exist_ok=True)
    files = [path for path in sorted(folder.rglob("*")) if path.is_file() and path.name not in ("Thumbs.db", "desktop.ini")]
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for number, path in enumerate(files, 1):
            archive.write(path, Path(folder.name) / path.relative_to(folder))
            if number % 500 == 0:
                print(f"{number}/{len(files)} files", flush=True)
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    Path(f"{target}.sha256").write_text(f"{digest.hexdigest()}  {target.name}\n")
    print(f"{target}: {target.stat().st_size / 1048576:,.0f} MB, {len(files)} files, sha256 {digest.hexdigest()}")


if __name__ == "__main__":
    main()
