# Handoff: migration_holdings

Status: working and tested on iteration_1. Written 2026-10-13. The code is
planned to move to a permanent home; this document lists what must change when
it does. See `README.md` for usage.

## Purpose

After a FOLIO holdings migration, holdings that could not be mapped to a real
location land in a catch-all "Migration" location. This tool recovers the
original source location (MARC 852$b) for those holdings and shows the
distribution, so the legacy-to-FOLIO location map can be corrected.

## How it works (single file, `migration_holdings.py`)

| Function | Role |
|---|---|
| `choose` | Numbered menu prompt |
| `ask_uuid` | Prompt and validate the location UUID |
| `collect_former_ids` | Streams the ndjson, returns de-duplicated `formerIds[0]` values for matching records |
| `readable_852` / `subfield_b` | Format an 852 field / extract its $b values |
| `code_notes` | Builds the `note` flags for suspicious location codes |
| `main` | Menus, scan, write outputs, print summary |

The ndjson is streamed one line at a time and the matching IDs are kept in a
set, so memory use is small. The MARC file is streamed with `pymarc`
`MARCReader`, and the 001 lookup is a set membership test.

## Test result (iteration_1)

Using `folio_holdings_transform_mfhd_holdings.json`,
`holdings_records_repaired.mrc` and UUID `dbdb909a-f783-4390-8c42-62d5fa3d6a28`:
6,751 matching JSON records, 6,751 found in MARC, 0 missing, 6,751 rows
written. One flagged code: `OFC  PER` (double space).

## Hardcoded items to change for the permanent home

- `ITERATIONS_DIR = /working/migration/iterations` (top of the script).
- Folder layout assumptions: `<iteration>/results/` for the transform JSON and
  `<iteration>/source_data/holdings/` for the MARC. Both are built in `main`.
- JSON filter: any `*.json` containing "holdings" (case-insensitive) except
  names containing "id_map" (e.g. `holdings_id_map.json`).
- `MAPPING_DIR = /working/migration/mapping_files`; the mapping file is chosen
  from a menu and must be tab-separated with a header row, legacy code in
  column 1 and FOLIO code in column 2. Matching is exact.
- Output goes to the script's own folder (`Path(__file__).parent`). This was a
  requirement. Outputs accumulate with timestamps and are never cleaned up, so
  a permanent home should probably use an output directory argument or a
  gitignored folder.
- There are no command-line arguments; everything is interactive. Adding
  `argparse` flags (iteration, json, mrc, uuid, out-dir) would make it
  scriptable.

## Assumptions and decisions

- Match on `permanentLocationId` only (decided with the requester).
- `formerIds[0]` is the legacy MARC 001. In the sample data `formerIds` looks
  like `["2", "Bib id: 2"]`, and the first entry is the holdings 001.
- MARC input is binary `.mrc`; output is TSV (requester preference).
- One output row per 852 field. If a record has multiple 852s, it produces
  multiple rows.
- "Distribution of 852$b" was interpreted as a count of every distinct value,
  not a filter on values containing "reference". This was confirmed by the
  requester's stated goal: finding location codes that failed to map.

## Map comparison (added later)

The counts file compares each 852$b value to the chosen mapping file's
`legacy_code` column. In the iteration_1 test with `locations.tsv`, 16 of 17
codes are `NOT IN MAP` (INT, Media, HCM MCC, HCM AHC, EBOOK and others). The
exception is `OFC  PER` (double space): `locations.tsv` has an exact entry for
it (mapped to `OFC PER`), yet those holdings still landed in Migration. This
suggests the migration tool normalises or strips whitespace in the map keys or
source values, so the double-space entry may be colliding with the `OFC PER`
entry. This is unconfirmed and worth checking in the migration tooling.

## Known limitations and risks

- `MARCReader(permissive=True)` silently drops unreadable records. A formerId
  that is "not found" may be a damaged MARC record, not a missing one.
- Only 852$b is reported. If the map keys on other subfields (e.g. 852$c), they
  are not in the distribution.
- 852 subfields with `None` or odd values are not specially handled.
- Records with a missing `formerIds` are skipped and only counted, not listed.
- `code_notes` near-duplicate detection compares only the codes within the
  current run's results.
- There are no automated tests. Verification so far was a manual run on
  iteration_1 with counts cross-checked (6,751 in = 6,751 found).
- Dependencies are not pinned in a requirements file.

## Suggested next steps

1. Add `argparse` options and an output-dir option.
2. Add a `requirements.txt` (`pymarc`).
3. Add a small unit test for `code_notes` and `collect_former_ids`.

## Model test folder

`working/` in the repo root is a model of the production layout, with sample
data for testing (iteration_1, the same data as the test result above):

```
working/migration/iterations/iteration_1/
  results/folio_holdings_transform_mfhd_holdings.json   (~41 MB)
  source_data/holdings/holdings_records.mrc             (~15 MB)
  mapping/locations.tsv                                 (copy of the map)
```

- It is listed in `.gitignore` (`working/`), so the data is not committed.
- The model keeps the map at `iterations/<iteration>/mapping/`, but the script
  still looks in `/working/migration/mapping_files/` (`MAPPING_DIR`). To run
  against the model, either point `ITERATIONS_DIR` and `MAPPING_DIR` at it or
  change the script to look in the per-iteration `mapping/` folder.

## Related files

- `/working/migration/mapping_files/locations.tsv`: the legacy-to-FOLIO map
  this report is meant to help fix.
- `iterations/<iteration>/results/folio_holdings_transform_*.json`: tool input.
- `iterations/<iteration>/source_data/holdings/*.mrc`: tool input.
