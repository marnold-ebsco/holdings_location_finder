#!/usr/bin/env python3
"""Report MARC 852 data for holdings that were migrated to a given location.

Steps:
  1. Pick an iteration, a folio_holdings_transform ndjson file, a MARC (.mrc)
     holdings file and enter the Migration location UUID.
  2. Collect formerIds[0] from every JSON record whose permanentLocationId
     equals the UUID.
  3. Find the MARC records whose 001 equals one of those values.
  4. Write a TSV: formerId, readable 852, 852$b.
"""
import csv
import json
import re
import sys
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

from pymarc import MARCReader

ITERATIONS_DIR = Path("/working/migration/iterations")
MAPPING_DIR = Path("/working/migration/mapping_files")


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
        value = input("Migration location UUID: ").strip().lower()
        try:
            return str(uuid.UUID(value))
        except ValueError:
            print("Not a valid UUID.")


def collect_former_ids(json_path, location_id):
    """Return (ordered list of formerIds[0], matched record count, skipped count)."""
    ids, seen = [], set()
    matched = skipped = 0
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
            if rec.get("permanentLocationId") != location_id:
                continue
            matched += 1
            former = rec.get("formerIds") or []
            if not former:
                skipped += 1
                continue
            value = str(former[0]).strip()
            if value not in seen:
                seen.add(value)
                ids.append(value)
    return ids, matched, skipped


def readable_852(field):
    return " ".join(f"${sf.code} {sf.value}" for sf in field.subfields)


def subfield_b(field):
    return " | ".join(field.get_subfields("b"))


def clean(text):
    """Keep TSV rows intact."""
    return re.sub(r"[\t\r\n]+", " ", text)


def code_notes(value, all_values):
    """Describe near-invisible problems in a location code."""
    notes = []
    if value != value.lstrip():
        notes.append("leading space")
    if value != value.rstrip():
        notes.append("trailing space")
    if re.search(r"\S {2,}\S", value):
        notes.append("multiple consecutive spaces")
    if re.search(r"[\t\r\n]", value):
        notes.append("tab/newline")
    if re.search(r"[\u00a0\u2000-\u200f\u2028\u2029\u202f\u205f\u3000\ufeff]", value):
        notes.append("non-breaking/zero-width/unicode space")
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value):
        notes.append("control character")
    if re.search(r"[^\x00-\x7f]", value) and not any("unicode" in n for n in notes):
        notes.append("non-ASCII character")
    if " | " in value:
        notes.append("multiple $b in one 852")
    norm = re.sub(r"\s+", " ", value.strip()).casefold()
    twins = [v for v in all_values if v != value and re.sub(r"\s+", " ", v.strip()).casefold() == norm]
    if twins:
        notes.append("near-duplicate of: " + "; ".join(repr(t) for t in twins))
    return "; ".join(notes)


def load_map(path):
    """Return {legacy_code: folio_code} from a TSV with a header row."""
    with open(path, encoding="utf-8", newline="") as fh:
        rows = csv.reader(fh, delimiter="\t")
        header = next(rows, [])
        if len(header) < 2:
            sys.exit(f"{path.name} needs at least two tab-separated columns.")
        return {r[0]: r[1] for r in rows if len(r) >= 2}


def norm(value):
    return re.sub(r"\s+", " ", value.strip()).casefold()


def map_status(value, mapping, norm_map):
    """Return (status, folio_code) for a source 852$b code."""
    if value in mapping:
        return "mapped", mapping[value]
    near = norm_map.get(norm(value))
    if near:
        return f"NOT IN MAP (near match: {near!r})", ""
    return "NOT IN MAP", ""


def main():
    iterations = sorted(p.name for p in ITERATIONS_DIR.iterdir() if p.is_dir())
    print("Iterations:")
    iteration = choose("Select iteration", iterations)

    base = ITERATIONS_DIR / iteration
    results_dir = base / "results"
    json_files = sorted(
        p for p in results_dir.glob("*.json") if "holdings" in p.name.lower() and "id_map" not in p.name.lower()
    )
    print("\nHoldings transform JSON files:")
    json_path = choose("Select JSON file", json_files, file_label)

    marc_dir = base / "source_data" / "holdings"
    marc_files = sorted(
        p for p in marc_dir.glob("*.mrc") if p.is_file() and p.stat().st_size > 0
    )
    print("\nMARC holdings files:")
    marc_path = choose("Select MARC file", marc_files, file_label)

    map_files = sorted(MAPPING_DIR.glob("*.tsv"))
    print("\nLocation mapping files:")
    map_path = choose("Select mapping file", map_files, file_label)
    mapping = load_map(map_path)
    norm_map = {norm(k): k for k in mapping}

    print()
    location_id = ask_uuid()

    print(f"\nScanning {json_path.name} ...")
    former_ids, matched, skipped = collect_former_ids(json_path, location_id)
    print(f"  {matched} records with permanentLocationId {location_id}")
    if skipped:
        print(f"  {skipped} of those had no formerIds and were skipped")
    if not former_ids:
        sys.exit("No formerIds found; nothing to look up.")
    wanted = set(former_ids)

    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    out_dir = Path(__file__).resolve().parent
    out_path = out_dir / f"migration_holdings_{stamp}.tsv"
    counts_path = out_dir / f"migration_holdings_{stamp}_852b_counts.tsv"
    b_counts = Counter()
    found = set()
    rows = 0
    print(f"Scanning {marc_path.name} ...")
    with open(marc_path, "rb") as fh, open(out_path, "w", encoding="utf-8") as out:
        out.write("formerId\t852\t852$b\n")
        reader = MARCReader(fh, to_unicode=True, force_utf8=True, permissive=True)
        for record in reader:
            if record is None:
                continue
            f001 = record.get("001")
            if f001 is None:
                continue
            key = f001.data.strip()
            if key not in wanted:
                continue
            found.add(key)
            for field in record.get_fields("852"):
                out.write(
                    f"{clean(key)}\t{clean(readable_852(field))}\t{clean(subfield_b(field))}\n"
                )
                b_counts[subfield_b(field)] += 1
                rows += 1

    with open(counts_path, "w", encoding="utf-8") as cf:
        cf.write("852$b\tcount\tmap_status\tfolio_code\tnote\n")
        for value, n in b_counts.most_common():
            status, folio = map_status(value, mapping, norm_map)
            cf.write(
                f"{clean(value)}\t{n}\t{clean(status)}\t{clean(folio)}"
                f"\t{code_notes(value, b_counts)}\n"
            )

    missing = [i for i in former_ids if i not in found]
    print("\nSummary")
    print(f"  formerIds searched : {len(wanted)}")
    print(f"  found in MARC      : {len(found)}")
    print(f"  not found in MARC  : {len(missing)}")
    print(f"  rows written       : {rows}")
    if missing:
        print(f"  first missing      : {', '.join(missing[:10])}")
    print("\n852$b counts")
    for value, n in b_counts.most_common():
        note = code_notes(value, b_counts)
        status, _ = map_status(value, mapping, norm_map)
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
