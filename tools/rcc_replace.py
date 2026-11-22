#!/usr/bin/env python3
"""Replace one file inside a Qt resource package (.rcc) and write a new package.

The ZATHROTH client's login background is /images/title.jpg inside
bin/graphics_resources.rcc. Example:

    python3 tools/rcc_replace.py bin/graphics_resources.rcc /images/title.jpg my_title.jpg -o graphics_resources.new.rcc

The input package is never modified. Keep the original as a backup, then copy the
new file over bin/graphics_resources.rcc. Works with Qt resource format versions 1 to 3.
"""

import argparse
import struct
import sys
import zlib


def parse(data):
    magic, version, tree_off, data_off, names_off = struct.unpack(">4sIIII", data[:20])
    if magic != b"qres" or version not in (1, 2, 3):
        raise SystemExit("Not a Qt resource package")
    header = 24 if version >= 3 else 20
    entry = 14 if version == 1 else 22

    def name_at(off):
        length = struct.unpack(">H", data[names_off + off: names_off + off + 2])[0]
        return data[names_off + off + 6: names_off + off + 6 + 2 * length].decode("utf-16-be")

    entries = []

    def walk(index, path):
        base = tree_off + index * entry
        name_off, flags = struct.unpack(">IH", data[base: base + 6])
        name = name_at(name_off) if index else ""
        full = f"{path}/{name}" if name else path
        if flags & 2:
            count, first = struct.unpack(">II", data[base + 6: base + 14])
            for child in range(count):
                walk(first + child, full)
        else:
            entries.append({"path": full, "flags": flags, "tree": base, "offset": struct.unpack(">I", data[base + 10: base + 14])[0]})

    walk(0, "")
    return version, header, tree_off, data_off, names_off, entries


def blob(data, data_off, entry):
    start = data_off + entry["offset"]
    size = struct.unpack(">I", data[start: start + 4])[0]
    return data[start: start + 4 + size]


def read_file(data, data_off, entry):
    stored = blob(data, data_off, entry)[4:]
    if entry["flags"] & 1:
        return zlib.decompress(stored[4:])
    if entry["flags"] & 4:
        raise SystemExit("zstd-compressed entries are not supported")
    return stored


def replace(data, target, new_bytes):
    version, header, tree_off, data_off, names_off, entries = parse(data)
    chosen = [e for e in entries if e["path"] == target]
    if not chosen:
        raise SystemExit(f"{target} is not in the package")
    chosen = chosen[0]

    # The three sections run from their own offset to the next one (or the end).
    order = sorted((("tree", tree_off), ("data", data_off), ("names", names_off)), key=lambda section: section[1])
    bounds = {}
    for index, (name, offset) in enumerate(order):
        bounds[name] = (offset, order[index + 1][1] if index + 1 < len(order) else len(data))
    names = data[bounds["names"][0]: bounds["names"][1]]
    tree = bytearray(data[bounds["tree"][0]: bounds["tree"][1]])

    # Rebuild the data section; every other file is copied as it was. Entries
    # with identical content may share one stored copy, and keep sharing it.
    new_chunk = struct.pack(">I", len(new_bytes)) + new_bytes
    by_offset = {}
    for entry in entries:
        by_offset.setdefault(entry["offset"], []).append(entry)
    pieces, position, placed = [], 0, {}
    for offset in sorted(by_offset):
        group = by_offset[offset]
        chunk = new_chunk if group == [chosen] else blob(data, data_off, group[0])
        placed[offset] = position
        pieces.append(chunk)
        position += len(chunk)
    chosen_position = placed.get(chosen["offset"]) if by_offset[chosen["offset"]] == [chosen] else position
    if chosen_position == position:  # the old copy is shared with other files: add a separate one
        pieces.append(new_chunk)
        position += len(new_chunk)
    for entry in entries:
        rel = entry["tree"] - tree_off
        tree[rel + 10: rel + 14] = struct.pack(">I", chosen_position if entry is chosen else placed[entry["offset"]])
    rel = chosen["tree"] - tree_off
    flags = struct.unpack(">H", tree[rel + 4: rel + 6])[0] & ~(1 | 4)  # stored uncompressed
    tree[rel + 4: rel + 6] = struct.pack(">H", flags)

    new_data = b"".join(pieces)
    new_names_off = header + len(new_data)
    new_tree_off = new_names_off + len(names)
    out = bytearray(data[:header])
    out[8:20] = struct.pack(">III", new_tree_off, header, new_names_off)
    return bytes(out) + new_data + names + bytes(tree)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package")
    ap.add_argument("path", help="path inside the package, for example /images/title.jpg")
    ap.add_argument("new_file")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    data = open(args.package, "rb").read()
    new = open(args.new_file, "rb").read()
    result = replace(data, args.path, new)
    # Read everything back before writing: the new file must come out byte for byte.
    version, header, tree_off, data_off, names_off, entries = parse(result)
    entry = [e for e in entries if e["path"] == args.path][0]
    assert read_file(result, data_off, entry) == new, "the replaced file does not read back"
    old_version, _, _, old_data_off, _, old_entries = parse(data)
    old = {e["path"]: read_file(data, old_data_off, e) for e in old_entries}
    for e in entries:
        if e["path"] != args.path:
            assert read_file(result, data_off, e) == old[e["path"]], f"{e['path']} changed"
    open(args.output, "wb").write(result)
    print(f"wrote {args.output}: {len(entries)} files, {args.path} is now {len(new)} bytes")


if __name__ == "__main__":
    sys.exit(main())
