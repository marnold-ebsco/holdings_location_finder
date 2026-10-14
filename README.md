# migration_holdings

Interactive tools that find holdings records that landed in the FOLIO
"Migration" location, and report the original source location data for them.
Use them to see which source location codes did not map, so the location map
can be fixed.

There are two scripts, depending on what the holdings were migrated from:

| Script | Source data | Location value reported |
|---|---|---|
| `migration_holdings.py` | MARC holdings (`.mrc`) | 852$b |
| `migration_holdings_tsv.py` | Source TSV (items) | a chosen column, default `Location` |

The first part of this README covers the MARC script. See
[TSV version](#tsv-version-migration_holdings_tsvpy) for the other.

## What it does

1. Reads a `folio_holdings_transform` ndjson file and collects `formerIds[0]`
   from every record whose `permanentLocationId` equals the Migration UUID.
2. Reads the MARC holdings (`.mrc`) file the transform was based on and finds
   the records whose 001 exactly equals one of those values.
3. Writes two TSV files (see Output).

## Requirements

- Python 3.12+
- `pymarc` (developed on 5.4.0): `pip install pymarc`

## Setup

```
./setup.sh
```

This creates `.venv` and installs `requirements.txt` (needs Python 3.12+).
`migration_holdings_tsv.py` uses only the standard library and needs no setup.

### Installing on an EC2 instance (Ubuntu)

Assumes Python 3.12+ and git are already installed, and that
`/working/migration/iterations` and `/working/migration/mapping_files` already
exist. The installer checks for Python and git but does not install them.

1. Clone the repo anywhere (for example your home folder) and run the installer:
   ```
   git clone https://github.com/marnold-ebsco/holdings_location_finder.git
   cd holdings_location_finder
   ./install_ec2.sh
   ```
   If the repo is private, clone with a GitHub token or deploy key, or copy the
   folder up with `scp` instead.
2. The installer creates `/working/migration/scripts` if it is missing, places
   the code in `/working/migration/scripts/holdings_migration_finder` (cloning
   it there when you ran it from somewhere else), and runs `setup.sh` to build
   `.venv`. You can delete the first clone afterwards.
3. Run the tools from the install folder (see *Usage* for the prompts). The
   iterations and mapping files are read from the existing folders:
   ```
   cd /working/migration/scripts/holdings_migration_finder
   .venv/bin/python migration_holdings.py        # MARC
   python3 migration_holdings_tsv.py             # TSV
   ```
   Outputs go in the install folder unless you pass `--out-dir`.

If the repo is already in `/working/migration/scripts/` (any folder name), the
installer uses it in place and does not clone again:

```
cd /working/migration/scripts/holdings_migration_finder
git pull                # optional, to get the latest code
./install_ec2.sh
```

If Python 3.12 is installed under another name, run
`PYTHON=/path/to/python3.12 ./install_ec2.sh`. The installer needs outbound
internet access for `git clone` and the `pip install`.

## Usage

```
.venv/bin/python migration_holdings.py
```

You are prompted for, in order:

| Prompt | Source |
|---|---|
| Iteration | Folders under `/working/migration/iterations/` |
| JSON file | `*.json` files with "holdings" in the name (excluding `*id_map*`) in `iterations/<iteration>/results/` |
| MARC file | Non-empty `*.mrc` files in `iterations/<iteration>/source_data/holdings/` |
| Location mapping file | `*.tsv` files in `mapping_files/`, a sibling of the iterations folder, e.g. `/working/migration/mapping_files/` (needs `legacy_code` and `folio_code` columns, header row first) |
| Migration location UUID | Typed in; validated as a UUID |

Choose from the numbered menus by entering the number. Press Ctrl-C to cancel.

### Command-line options

Every option is optional; anything left off is chosen from the menu or prompt above.

| Option | Purpose |
|---|---|
| `--iterations-dir PATH` | Folder of iterations (default `/working/migration/iterations`) |
| `--iteration NAME` | Iteration folder name |
| `--json PATH` | Transform ndjson file (overrides `--iteration`) |
| `--mrc PATH` | MARC holdings file (overrides `--iteration`) |
| `--mapping PATH` | Location mapping TSV |
| `--no-map` | Skip the mapping comparison (counts file has only `852$b`, `count`, `note`) |
| `--location-uuid UUID` | Migration location UUID |
| `--out-dir PATH` | Output folder (default: the script folder; created if missing) |

With `--json`, `--mrc`, `--location-uuid` and one of `--mapping`/`--no-map`, the
script runs with no prompts.

### Tests

```
pip install -r requirements.txt
python -m pytest
flake8
```

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

## TSV version (`migration_holdings_tsv.py`)

Use this when the holdings were built from a TSV rather than MARC. It uses only
the standard library, so it needs no `.venv`: `python3 migration_holdings_tsv.py`.

### What it does

1. Reads the `folio_holdings_transform` ndjson file and collects
   `formerIds[1:]` (the item IDs) from every record whose `permanentLocationId`
   equals the Migration UUID. In the TSV transform, `formerIds[0]` is the bib
   ID and the rest are item IDs.
2. Reads the source TSV and keeps each row whose item-ID column equals one of
   those IDs (exact match, whitespace stripped).
3. Writes the matching rows and a count of the raw location values.

### Prompts

| Prompt | Source |
|---|---|
| Iteration | Folders under `/working/migration/iterations/` |
| JSON file | `*.json` with "holdings" in the name (excluding `*id_map*`) in `iterations/<iteration>/results/`. Pick the `..._csv_holdings.json` file |
| TSV file | Non-empty `*.tsv` in `iterations/<iteration>/source_data/holdings/` |
| Location mapping file | `*.tsv` in `/working/migration/mapping_files/` (sibling of `iterations`; header row, legacy code in column 1, FOLIO code in column 2) |
| Item ID / location column | Defaults to `RecordNumber(Item)` and `Location` if the header has them, otherwise a menu |
| Migration location UUID | Typed in; validated. There is **no default**, because it differs per tenant |

### Command-line options

| Option | Purpose |
|---|---|
| `--iterations-dir PATH`, `--iteration NAME` | As for the MARC script |
| `--json PATH`, `--tsv PATH` | Input files (override `--iteration`) |
| `--item-col NAME`, `--location-col NAME` | TSV column names |
| `--mapping PATH` / `--no-map` | Mapping file, or skip the comparison |
| `--location-uuid UUID` | Migration location UUID |
| `--out-dir PATH` | Output folder (default: the script folder) |

### Output

Written to the script folder with a shared timestamp:

- `migration_holdings_tsv_<timestamp>.tsv`: one row per matched TSV (item)
  row, with all the original columns plus a `note` column (same checks as the
  MARC `note` column).
- `migration_holdings_tsv_<timestamp>_location_counts.tsv`: each raw location
  value with `count` (item rows), `map_status`, `folio_code` and `note`.

The terminal summary shows holdings found, item IDs searched, found and
missing, and the location counts.

### Behaviour to know about

- Matching is on item ID only, not bib ID or bib + location.
- A holdings record covering several bibs has a TSV bib cell like `b1;b2`, and
  its extra bib IDs also appear in `formerIds`. Those are not reported as
  missing items.
- Records with no item IDs in `formerIds` are skipped and counted.
- The counts are per item row, so they can exceed the number of holdings.

### Tests

```
.venv/bin/python -m pytest test_migration_holdings_tsv.py
```

## Files

- `migration_holdings.py`: the MARC tool
- `migration_holdings_tsv.py`: the TSV tool
- `test_migration_holdings.py`, `test_migration_holdings_tsv.py`: PyTest tests
- `setup.sh`: creates `.venv` and installs `requirements.txt`
- `install_ec2.sh`: Ubuntu EC2 installer; checks Python and git, installs into `/working/migration/scripts/`, runs `setup.sh`
- `HANDOFF.md`: design notes, assumptions and open items for the next owner
