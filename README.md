# migration_holdings

Interactive tool that finds holdings records that landed in the FOLIO
"Migration" location, and reports the original MARC 852 data for them. Use it
to see which source location codes (852$b) did not map, so the location map can
be fixed.

## What it does

1. Reads a `folio_holdings_transform` ndjson file and collects `formerIds[0]`
   from every record whose `permanentLocationId` equals the Migration UUID.
2. Reads the MARC holdings (`.mrc`) file the transform was based on and finds
   the records whose 001 exactly equals one of those values.
3. Writes two TSV files (see Output).

## Requirements

- Python 3.9+ (developed on 3.14)
- `pymarc` (developed on 5.4.0): `pip install pymarc`

## Usage

```
python3 migration_holdings.py
```

You are prompted for, in order:

| Prompt | Source |
|---|---|
| Iteration | Folders under `/working/migration/iterations/` |
| JSON file | `*.json` files with "holdings" in the name (excluding `*id_map*`) in `iterations/<iteration>/results/` |
| MARC file | Non-empty `*.mrc` files in `iterations/<iteration>/source_data/holdings/` |
| Location mapping file | `*.tsv` files in `/working/migration/mapping_files/` (needs `legacy_code` and `folio_code` columns, header row first) |
| Migration location UUID | Typed in; validated as a UUID |

Choose from the numbered menus by entering the number. Press Ctrl-C to cancel.

## Output

Written to the same folder as the script, with a shared timestamp:

- `migration_holdings_<timestamp>.tsv` has one row per 852 field, with
  columns `formerId`, `852` and `852$b`. The `852` column is human readable:
  each subfield is shown as `$<code> <value>`, for example
  `$b Media $k AV $h HD38 $i V66`.
- `migration_holdings_<timestamp>_852b_counts.tsv` lists each distinct 852$b
  value with its record count (most frequent first), `map_status`, `folio_code`
  and a `note` column. `map_status` is `mapped`, `NOT IN MAP`, or
  `NOT IN MAP (near match: '<code>')` when the map has the same code differing
  only by case or whitespace.

The run summary printed to the terminal shows the same counts, plus how many
formerIds were searched, found and missing.

### The `note` column

Flags location codes that look right but are not, because the problem is
almost invisible: leading/trailing spaces, multiple consecutive spaces,
tabs/newlines, non-breaking/zero-width/unicode spaces, control or other
non-ASCII characters, more than one $b in a single 852, and near-duplicates
that differ only by case or whitespace (the other variant is named). Example:
`OFC  PER` (two spaces) is flagged "multiple consecutive spaces".

## Behaviour to know about

- Only `permanentLocationId` is checked; `temporaryLocationId` is ignored.
- Records with a missing or empty `formerIds` are skipped and counted in the
  summary.
- The 001 is whitespace-stripped before matching, and the match is exact.
- Corrupt MARC records are tolerated (`permissive=True`); records that cannot
  be read are silently skipped, so a formerId can show as "not found" for that
  reason.
- Counts are per 852 field. Normally this equals per record.

## Files

- `migration_holdings.py`: the tool
- `HANDOFF.md`: design notes, assumptions and open items for the next owner
