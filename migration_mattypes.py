#!/usr/bin/env python3
"""Report source rows for items that were migrated to a given material type.

Items counterpart of migration_holdings_tsv.py. Use it to find the legacy
material-type values behind items that landed in the catch-all "Migration"
material type, so the material-type map can be corrected.

Steps:
  1. Pick an iteration, a folio_item_transform ndjson file, a source TSV
     (from source_data/items) and enter the Migration material type UUID
     (no default; it varies by tenant).
  2. Collect the formerIds (item IDs) from every JSON record whose
     materialTypeId equals the UUID.
  3. Find the TSV rows whose item-ID column equals one of those values.
  4. Write the matching rows, plus counts of the raw material-type values.
"""
import argparse
import csv
import json
import re
import sys
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

ITERATIONS_DIR = Path("/working/migration/iterations")
MAPPING_DIRNAME = "mapping_files"  # sibling of the iterations folder
TSV_SUBDIR = "items"  # under <iteration>/source_data
DEFAULT_ITEM_COL = "RecordNumber(Item)"
DEFAULT_TYPE_COL = "Material Type"


def choose(prompt, options, label=str):
    """Show a numbered menu and return the chosen option."""
    if not options:
        sys.exit(f"Nothing to choose from for: {prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {label(opt)}")
    while True:
        answer = input(f"{prompt} [1-{len(options)}]: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1]
        print("Invalid selection.")


def file_label(path):
    stat = path.stat()
    stamp = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    return f"{path.name}  ({stat.st_size / 1_000_000:.1f} MB, {stamp})"


def ask_uuid():
    while True:
        value = input("Migration material type UUID: ").strip().lower()
        try:
            return str(uuid.UUID(value))
        except ValueError:
            print("Not a valid UUID.")


def clean(text):
    """Keep TSV rows intact."""
    return re.sub(r"[\t\r\n]+", " ", text)


def norm(value):
    return re.sub(r"\s+", " ", value.strip()).casefold()


def code_notes(value, all_values):
    """Describe near-invisible problems in a material-type value."""
    notes = []
    if value != value.lstrip():
        notes.append("leading space")
    if value != value.rstrip():
        notes.append("trailing space")
    if re.search(r"\S {2,}\S", value):
        notes.append("multiple consecutive spaces")
    if re.search(r"[\t\r\n]", value):
        notes.append("tab/newline")
    if re.search(r"[  -‏    　﻿]", value):
        notes.append("non-breaking/zero-width/unicode space")
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value):
        notes.append("control character")
    if re.search(r"[^\x00-\x7f]", value) and not any("unicode" in n for n in notes):
        notes.append("non-ASCII character")
    twins = [v for v in all_values if v != value and norm(v) == norm(value)]
    if twins:
        notes.append("near-duplicate of: " + "; ".join(repr(t) for t in twins))
    return "; ".join(notes)


def load_map(path):
    """Return {legacy_value: folio_name} from a TSV with a header row."""
    with open(path, encoding="utf-8", newline="") as fh:
        rows = csv.reader(fh, delimiter="\t")
        header = next(rows, [])
        if len(header) < 2:
            sys.exit(f"{path.name} needs at least two tab-separated columns.")
        return {r[0]: r[1] for r in rows if len(r) >= 2}


def map_status(value, mapping, norm_map):
    """Return (status, folio_name) for a source material-type value."""
    if value in mapping:
        return "mapped", mapping[value]
    near = norm_map.get(norm(value))
    if near:
        return f"NOT IN MAP (near match: {near!r})", ""
    return "NOT IN MAP", ""


def collect_item_ids(json_path, type_id):
    """Return (item IDs in order, matched record count, records without former IDs)."""
    ids, seen = [], set()
    matched = no_items = 0
    with open(json_path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                print(f"  warning: line {lineno} is not valid JSON, skipped")
                continue
            if rec.get("materialTypeId") != type_id:
                continue
            matched += 1
            items = [str(v).strip() for v in (rec.get("formerIds") or [])]
            items = [v for v in items if v]
            if not items:
                no_items += 1
                continue
            for value in items:
                if value not in seen:
                    seen.add(value)
                    ids.append(value)
    return ids, matched, no_items


def pick_column(prompt, header, default, given):
    """Return the column name from --option, a default header match, or a menu."""
    if given:
        if given not in header:
            sys.exit(f"Column {given!r} not in TSV header.")
        return given
    if default in header:
        return default
    print(f"\n{prompt}")
    return choose("Select column", header)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Report source TSV rows for items in the Migration material type. "
        "Any option left off is chosen from an interactive menu or prompt."
    )
    ap.add_argument("--iterations-dir", type=Path, default=ITERATIONS_DIR,
                    help=f"folder of iterations (default {ITERATIONS_DIR})")
    ap.add_argument("--iteration", help="iteration folder name")
    ap.add_argument("--json", type=Path, dest="json_path",
                    help="item transform ndjson file (overrides --iteration)")
    ap.add_argument("--tsv", type=Path, dest="tsv_path",
                    help="source TSV file (overrides --iteration)")
    ap.add_argument("--item-col", help=f"item ID column (default {DEFAULT_ITEM_COL})")
    ap.add_argument("--type-col",
                    help=f"material type column (default {DEFAULT_TYPE_COL})")
    ap.add_argument("--mapping", type=Path, dest="map_path",
                    help="material type mapping TSV (default: menu of <iterations-dir>/../mapping_files)")
    ap.add_argument("--no-map", action="store_true",
                    help="skip the mapping comparison")
    ap.add_argument("--type-uuid",
                    help="Migration material type UUID (prompted if omitted)")
    ap.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent,
                    help="output folder (default: the script folder)")
    args = ap.parse_args(argv)
    if args.map_path and args.no_map:
        ap.error("--mapping and --no-map cannot be used together")
    if args.type_uuid:
        try:
            args.type_uuid = str(uuid.UUID(args.type_uuid.strip().lower()))
        except ValueError:
            ap.error("--type-uuid is not a valid UUID")
    for name in ("json_path", "tsv_path", "map_path"):
        path = getattr(args, name)
        if path and not path.is_file():
            ap.error(f"file not found: {path}")
    return args


def main(argv=None):
    args = parse_args(argv)
    base = None
    need_menu = not (args.json_path and args.tsv_path and (args.map_path or args.no_map))
    if need_menu:
        iteration = args.iteration
        if not iteration:
            iterations = sorted(p.name for p in args.iterations_dir.iterdir() if p.is_dir())
            print("Iterations:")
            iteration = choose("Select iteration", iterations)
        base = args.iterations_dir / iteration

    json_path = args.json_path
    if not json_path:
        json_files = sorted(
            p for p in (base / "results").glob("*.json")
            if "item" in p.name.lower() and "id_map" not in p.name.lower()
        )
        print("\nItem transform JSON files:")
        json_path = choose("Select JSON file", json_files, file_label)

    tsv_path = args.tsv_path
    if not tsv_path:
        tsv_files = [
            p for p in sorted((base / "source_data" / TSV_SUBDIR).glob("*.tsv"))
            if p.stat().st_size > 0
        ]
        print(f"\nSource TSV files (source_data/{TSV_SUBDIR}):")
        tsv_path = choose("Select TSV file", tsv_files, file_label)

    mapping = {}
    if not args.no_map:
        map_path = args.map_path
        if not map_path:
            map_files = sorted((args.iterations_dir.parent / MAPPING_DIRNAME).glob("*.tsv"))
            print("\nMaterial type mapping files:")
            map_path = choose("Select mapping file", map_files, file_label)
        mapping = load_map(map_path)
    norm_map = {norm(k): k for k in mapping}

    with open(tsv_path, encoding="utf-8", newline="") as fh:
        header = next(csv.reader(fh, delimiter="\t"), [])
    item_col = pick_column("Item ID column:", header, DEFAULT_ITEM_COL, args.item_col)
    type_col = pick_column("Material type column:", header, DEFAULT_TYPE_COL, args.type_col)
    bib_col = header[0]

    print()
    type_id = args.type_uuid or ask_uuid()

    print(f"\nScanning {json_path.name} ...")
    item_ids, matched, no_items = collect_item_ids(json_path, type_id)
    print(f"  {matched} records with materialTypeId {type_id}")
    if no_items:
        print(f"  {no_items} of those had no formerIds and were skipped")
    if not item_ids:
        sys.exit("No item IDs found; nothing to look up.")
    wanted = set(item_ids)

    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"migration_mattypes_{stamp}.tsv"
    counts_path = out_dir / f"migration_mattypes_{stamp}_type_counts.tsv"
    type_counts = Counter()
    found, bibs = set(), set()
    matched_rows = []
    print(f"Scanning {tsv_path.name} ...")
    with open(tsv_path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            key = (row.get(item_col) or "").strip()
            if key not in wanted:
                continue
            found.add(key)
            # multi-bib rows ("b1;b2") put the extra bib IDs in formerIds too
            bibs.update(t.strip() for t in (row.get(bib_col) or "").split(";"))
            value = row.get(type_col) or ""
            type_counts[value] += 1
            matched_rows.append((row, value))

    with open(out_path, "w", encoding="utf-8") as out:
        out.write("\t".join(header) + "\tnote\n")
        for row, value in matched_rows:
            cells = [clean(row.get(h) or "") for h in header]
            note = clean(code_notes(value, type_counts))
            out.write("\t".join(cells) + "\t" + note + "\n")

    with open(counts_path, "w", encoding="utf-8") as cf:
        if args.no_map:
            cf.write("material_type\tcount\tnote\n")
        else:
            cf.write("material_type\tcount\tmap_status\tfolio_name\tnote\n")
        for value, n in type_counts.most_common():
            note = clean(code_notes(value, type_counts))
            if args.no_map:
                cf.write(f"{clean(value)}\t{n}\t{note}\n")
                continue
            status, folio = map_status(value, mapping, norm_map)
            cf.write(f"{clean(value)}\t{n}\t{clean(status)}\t{clean(folio)}\t{note}\n")

    missing = [i for i in item_ids if i not in found and i not in bibs]
    print("\nSummary")
    print(f"  items in mat. type  : {matched}")
    print(f"  item IDs searched    : {len(wanted)}")
    print(f"  found in TSV         : {len(found)}")
    print(f"  not found in TSV     : {len(missing)}")
    print(f"  rows written         : {len(matched_rows)}")
    if missing:
        print(f"  first missing        : {', '.join(missing[:10])}")
    print("\nMaterial type counts")
    for value, n in type_counts.most_common():
        note = code_notes(value, type_counts)
        status = "mapped" if args.no_map else map_status(value, mapping, norm_map)[0]
        flag = f"   <-- {note}" if note else ""
        if status != "mapped":
            flag += f"   [{status}]"
        print(f"  {value or '(empty)'}: {n}{flag}")
    print(f"\nOutput: {out_path}")
    print(f"Counts: {counts_path}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        sys.exit("\nCancelled.")
