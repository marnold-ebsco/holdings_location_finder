# Handoff: migration_holdings

Status: working and tested on iteration_1. Written 2026-10-13; TSV version and
setup added 2026-10-14. Sections below cover the MARC script (`migration_holdings.py`)
unless titled otherwise; the TSV script has its own section. The code is
planned to move to a permanent home; this document lists what must change when
it does. See `README.md` for usage.

## Purpose

After a FOLIO holdings migration, holdings that could not be mapped to a real
location land in a catch-all "Migration" location. This tool recovers the
original source location (MARC 852$b, or a TSV location column) for those holdings and shows the
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
- `MAPPING_DIRNAME = mapping_files` (sibling of the iterations folder); the mapping file is chosen
  from a menu and must be tab-separated with a header row, legacy code in
  column 1 and FOLIO code in column 2. Matching is exact.
- Output goes to the script's own folder (`Path(__file__).parent`). This was a
  requirement. Outputs accumulate with timestamps and are never cleaned up, so
  a permanent home should probably use an output directory argument or a
  gitignored folder.
- Every prompt has an `argparse` flag, so the script can run non-interactively
  (see `README.md`).

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
- Dependencies are only lower-bounded in `requirements.txt` (`pymarc>=5.4`).

## Command-line options, tests, requirements (added later)

`argparse` options now exist (see README); the old hardcoded-path and
interactive-only items above are therefore partly resolved: paths can be
overridden, and `--out-dir` controls output. `requirements.txt` lists
`pymarc`, `pytest` and `flake8`. `test_migration_holdings.py` (PyTest, 15
tests) covers `code_notes`, `collect_former_ids`, the map helpers, argument
validation and two end-to-end runs on synthetic data. `.flake8` sets a
120-character line length.

A run on the model data (iteration_1) found 6,738 of 6,751 formerIds and
wrote 6,741 rows. The 13 not found are multi-part IDs (`-2`, `-3` suffixes)
and are known and not a concern.

## TSV version (`migration_holdings_tsv.py`, added 2026-10-14)

Same purpose as the MARC script, for tenants whose holdings were built from a
source TSV (`combined_items_prepped.tsv`, one row per item) instead of MARC.
Standard library only. Tests: `test_migration_holdings_tsv.py` (10 tests).

Key facts from the iteration_1 data, which drive the design:

- The input is `folio_holdings_transform_csv_holdings.json`, not the `mfhd`
  file. In this transform `formerIds[0]` is the **bib** ID (`b1000001x`) and
  `formerIds[1:]` are **item** IDs (`i1000001x`), which match TSV columns
  `RecordNumber(Bibliographic)` and `RecordNumber(Item)`.
- Matching is on **item ID only** (decided with the requester). One bib can
  have several item rows with different locations, so a bib match would pull
  in rows that are not in the Migration holdings. Bib + location matching was
  considered and rejected.
- A holdings record can cover several bibs. The TSV bib cell is then `b1;b2`
  and the extra bib IDs are also in `formerIds`. They are not item IDs, so the
  script does not report them as missing.
- The location column is `Location` (confirmed). The Migration UUID has **no
  default** because it differs per tenant.
- Output is one row per matched item row plus a `note` column, and a counts
  file by raw location (`..._location_counts.tsv`), with the same mapping
  comparison as the MARC script. See `README.md` for usage.

Test result (iteration_1, UUID `2cc9b294-5d1d-4eed-bf22-0f03e61d2ec5`): 31
holdings records, 30 item rows found, 0 missing. Locations: `none` 27 and
`zzzzz` 3, both `NOT IN MAP` in `locations_wts.tsv`.

The helper functions (`choose`, `ask_uuid`, `load_map`, `norm`, `code_notes`,
`map_status`) are copied from `migration_holdings.py`, not imported, so the TSV
script does not need `pymarc`. If the two move to a permanent home, consider a
shared module. `ask_uuid` and `code_notes` differ slightly (no default UUID;
no "multiple $b" note).

## Setup and layout changes (2026-10-14)

- `setup.sh` creates `.venv` and installs `requirements.txt` (needs Python
  3.12+). `migration_holdings.py` exits with a hint if `pymarc` is missing.
- The mapping folder is now `mapping_files/`, a **sibling of `iterations/`**
  (`<iterations-dir>/../mapping_files`), for both scripts. It follows
  `--iterations-dir` rather than a fixed path. The model data was moved to
  match, and `MAPPING_DIR` became `MAPPING_DIRNAME`.
- `install_ec2.sh` installs on an Ubuntu EC2 instance: checks that Python 3.12+ and
  git exist (it installs nothing), creates `/working/migration/scripts` if
  missing, puts the repo in `/working/migration/scripts/holdings_migration_finder`
  (cloning if run from elsewhere), then runs `setup.sh`. It assumes
  `iterations/` and `mapping_files/` already exist. It has NOT been run on a
  real EC2 instance, only syntax-checked; test it there before relying on it.
- Output stays in the script folder by default for both scripts
  (`--out-dir` overrides).

## Suggested next steps

1. Decide whether to share the helpers between the two scripts.
2. Add a `pyproject.toml` with console entry points if the code moves to a
   permanent home.

## Model test folder

`working/` in the repo root is a model of the production layout, with sample
data for testing (iteration_1):

```
working/migration/
  iterations/iteration_1/
    results/folio_holdings_transform_mfhd_holdings.json   (MARC version input)
    results/folio_holdings_transform_csv_holdings.json    (TSV version input)
    source_data/holdings/holdings_records.mrc             (MARC version input)
    source_data/holdings/combined_items_prepped.tsv       (TSV version input)
  mapping_files/locations.tsv, locations_wts.tsv
```

- It is listed in `.gitignore` (`working/`), so the data is not committed.
- Run against it with `--iterations-dir working/migration/iterations`. The
  mapping menu then reads `working/migration/mapping_files/`.
- The MARC version was tested with UUID `dbdb909a-f783-4390-8c42-62d5fa3d6a28`
  and `locations.tsv`; the TSV version with the UUID above and
  `locations_wts.tsv`.

## Related files

- `<migration>/mapping_files/*.tsv`: the legacy-to-FOLIO maps these reports are
  meant to help fix.
- `iterations/<iteration>/results/folio_holdings_transform_*.json`: tool input.
- `iterations/<iteration>/source_data/holdings/*.mrc` or `*.tsv`: tool input.
