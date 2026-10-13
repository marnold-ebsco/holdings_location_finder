import json

import pytest
from pymarc import Field, Record, Subfield

import migration_holdings as mh

LOC = "dbdb909a-f783-4390-8c42-62d5fa3d6a28"


def write_json(path, recs):
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")


def make_mrc(path, items):
    """items: list of (001, 852$b)."""
    with open(path, "wb") as fh:
        for f001, b in items:
            rec = Record()
            rec.add_field(Field(tag="001", data=f001))
            rec.add_field(Field(tag="852", indicators=[" ", " "],
                                subfields=[Subfield("b", b), Subfield("h", "HD1")]))
            fh.write(rec.as_marc())


# --- code_notes -------------------------------------------------------------

def test_code_notes_clean():
    assert mh.code_notes("OFC PER", ["OFC PER"]) == ""


def test_code_notes_double_space():
    assert "multiple consecutive spaces" in mh.code_notes("OFC  PER", [])


def test_code_notes_leading_trailing():
    assert "leading space" in mh.code_notes(" A", [])
    assert "trailing space" in mh.code_notes("A ", [])


def test_code_notes_nbsp_and_nonascii():
    assert "unicode space" in mh.code_notes("A B", [])
    assert "non-ASCII" in mh.code_notes("Café", [])


def test_code_notes_near_duplicate():
    note = mh.code_notes("OFC  PER", ["OFC  PER", "OFC PER"])
    assert "near-duplicate of: 'OFC PER'" in note


def test_code_notes_multiple_b():
    assert "multiple $b" in mh.code_notes("A | B", [])


# --- collect_former_ids -----------------------------------------------------

def test_collect_former_ids(tmp_path):
    p = tmp_path / "h.json"
    write_json(p, [
        {"permanentLocationId": LOC, "formerIds": ["1", "Bib id: 1"]},
        {"permanentLocationId": LOC, "formerIds": ["1"]},
        {"permanentLocationId": LOC, "formerIds": []},
        {"permanentLocationId": "other", "formerIds": ["9"]},
        {"permanentLocationId": LOC, "formerIds": [" 2 "]},
    ])
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("not json\n\n")
    ids, matched, skipped = mh.collect_former_ids(p, LOC)
    assert ids == ["1", "2"]
    assert matched == 4
    assert skipped == 1


# --- map helpers ------------------------------------------------------------

def test_map_status():
    mapping = {"OFC  PER": "OFC PER", "Main": "main"}
    nm = {mh.norm(k): k for k in mapping}
    assert mh.map_status("Main", mapping, nm) == ("mapped", "main")
    assert mh.map_status("MAIN", mapping, nm)[0] == "NOT IN MAP (near match: 'Main')"
    assert mh.map_status("zzz", mapping, nm) == ("NOT IN MAP", "")


def test_load_map(tmp_path):
    p = tmp_path / "m.tsv"
    p.write_text("legacy_code\tfolio_code\nA\tB\nbad\n", encoding="utf-8")
    assert mh.load_map(p) == {"A": "B"}


# --- parse_args -------------------------------------------------------------

def test_parse_args_normalises_uuid(tmp_path):
    args = mh.parse_args(["--location-uuid", LOC.upper()])
    assert args.location_uuid == LOC


def test_parse_args_bad_uuid():
    with pytest.raises(SystemExit):
        mh.parse_args(["--location-uuid", "nope"])


def test_parse_args_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        mh.parse_args(["--json", str(tmp_path / "missing.json")])


def test_parse_args_map_conflict(tmp_path):
    m = tmp_path / "m.tsv"
    m.write_text("a\tb\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        mh.parse_args(["--mapping", str(m), "--no-map"])


# --- end to end -------------------------------------------------------------

def run(tmp_path, extra, capsys):
    j, m, out = tmp_path / "h.json", tmp_path / "h.mrc", tmp_path / "out"
    write_json(j, [
        {"permanentLocationId": LOC, "formerIds": ["1"]},
        {"permanentLocationId": LOC, "formerIds": ["2"]},
        {"permanentLocationId": LOC, "formerIds": ["3"]},
    ])
    make_mrc(m, [("1", "Media"), ("2", "Media"), ("4", "Other")])
    mh.main(["--json", str(j), "--mrc", str(m), "--location-uuid", LOC,
             "--out-dir", str(out)] + extra)
    return out, capsys.readouterr().out


def test_main_with_map(tmp_path, capsys):
    mp = tmp_path / "locations.tsv"
    mp.write_text("legacy_code\tfolio_code\nMedia\tmedia\n", encoding="utf-8")
    out, text = run(tmp_path, ["--mapping", str(mp)], capsys)
    main_tsv = next(out.glob("migration_holdings_??????*[0-9].tsv"))
    lines = main_tsv.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "formerId\t852\t852$b"
    assert len(lines) == 3
    counts = next(out.glob("*_852b_counts.tsv")).read_text(encoding="utf-8")
    assert "Media\t2\tmapped\tmedia\t" in counts
    assert "not found in MARC  : 1" in text


def test_main_no_map(tmp_path, capsys):
    out, _ = run(tmp_path, ["--no-map"], capsys)
    counts = next(out.glob("*_852b_counts.tsv")).read_text(encoding="utf-8")
    assert counts.splitlines()[0] == "852$b\tcount\tnote"
