import json

import pytest

import migration_holdings_tsv as mt

LOC = "2cc9b294-5d1d-4eed-bf22-0f03e61d2ec5"
OTHER = "9a72cb58-7234-40bd-9e4f-cee79352f2f7"
HEADER = ["RecordNumber(Bibliographic)", "RecordNumber(Item)", "Location"]


def write_json(path, recs):
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")


def write_tsv(path, rows, header=HEADER):
    lines = ["\t".join(header)] + ["\t".join(r) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_collect_item_ids(tmp_path):
    p = tmp_path / "h.json"
    write_json(p, [
        {"permanentLocationId": LOC, "formerIds": ["b1", "i1", "i2"]},
        {"permanentLocationId": LOC, "formerIds": ["b2", "i2", "i3"]},
        {"permanentLocationId": LOC, "formerIds": ["b3"]},
        {"permanentLocationId": LOC},
        {"permanentLocationId": OTHER, "formerIds": ["b4", "i4"]},
    ])
    ids, matched, no_items = mt.collect_item_ids(p, LOC)
    assert ids == ["i1", "i2", "i3"]
    assert matched == 4
    assert no_items == 2


def test_collect_skips_bad_json(tmp_path, capsys):
    p = tmp_path / "h.json"
    good = json.dumps({"permanentLocationId": LOC, "formerIds": ["b1", "i1"]})
    p.write_text("not json\n" + good + "\n")
    ids, matched, _ = mt.collect_item_ids(p, LOC)
    assert ids == ["i1"] and matched == 1
    assert "not valid JSON" in capsys.readouterr().out


def test_ask_uuid_has_no_default(monkeypatch, capsys):
    answers = iter(["", "nope", LOC.upper()])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert mt.ask_uuid() == LOC
    assert capsys.readouterr().out.count("Not a valid UUID") == 2


def test_uuid_flag_validated():
    with pytest.raises(SystemExit):
        mt.parse_args(["--location-uuid", "bad"])


def test_map_status():
    mapping = {"pm": "pm"}
    nm = {mt.norm(k): k for k in mapping}
    assert mt.map_status("pm", mapping, nm) == ("mapped", "pm")
    assert mt.map_status("PM ", mapping, nm)[0].startswith("NOT IN MAP (near")
    assert mt.map_status("zz", mapping, nm) == ("NOT IN MAP", "")


def test_code_notes():
    assert mt.code_notes("pm", ["pm"]) == ""
    assert "multiple consecutive spaces" in mt.code_notes("a  b", [])
    assert "near-duplicate" in mt.code_notes("pm", ["pm", "PM "])


def test_end_to_end(tmp_path, capsys):
    rows = [
        ["b1", "i1", "xx"],
        ["b1", "i2", "xx"],
        ["b1", "i9", "pm"],  # same bib, not in a migration holdings record
        ["b2", "i3", "yy"],
    ]
    recs = [
        {"permanentLocationId": LOC, "formerIds": ["b1", "i1", "i2", "i7"]},
        {"permanentLocationId": LOC, "formerIds": ["b2", "i3"]},
    ]
    j, t, m = tmp_path / "h.json", tmp_path / "s.tsv", tmp_path / "map.tsv"
    write_json(j, recs)
    write_tsv(t, rows)
    m.write_text("Location\tfolio_code\npm\tpm\n")
    out = tmp_path / "out"
    mt.main(["--json", str(j), "--tsv", str(t), "--mapping", str(m),
             "--location-uuid", LOC, "--out-dir", str(out)])
    main_out, counts = sorted(out.iterdir())
    lines = main_out.read_text().splitlines()
    assert lines[0].endswith("\tnote")
    assert len(lines) == 4  # header + 3 rows; i9 excluded
    cl = counts.read_text().splitlines()
    assert cl[0].startswith("location\tcount\tmap_status")
    assert cl[1].startswith("xx\t2\tNOT IN MAP")
    assert cl[2].startswith("yy\t1\tNOT IN MAP")
    text = capsys.readouterr().out
    assert "not found in TSV     : 1" in text
    assert "first missing        : i7" in text


def test_no_map(tmp_path):
    j, t = tmp_path / "h.json", tmp_path / "s.tsv"
    write_json(j, [{"permanentLocationId": LOC, "formerIds": ["b1", "i1"]}])
    write_tsv(t, [["b1", "i1", "xx"]])
    out = tmp_path / "out"
    mt.main(["--json", str(j), "--tsv", str(t), "--no-map",
             "--location-uuid", LOC, "--out-dir", str(out)])
    counts = [p for p in out.iterdir() if "counts" in p.name][0]
    assert counts.read_text().splitlines() == ["location\tcount\tnote", "xx\t1\t"]


def test_missing_column_exits(tmp_path):
    j, t = tmp_path / "h.json", tmp_path / "s.tsv"
    write_json(j, [{"permanentLocationId": LOC, "formerIds": ["b1", "i1"]}])
    write_tsv(t, [["b1", "i1", "xx"]])
    with pytest.raises(SystemExit):
        mt.main(["--json", str(j), "--tsv", str(t), "--no-map",
                 "--item-col", "Nope", "--location-uuid", LOC,
                 "--out-dir", str(tmp_path / "o")])


def test_multi_bib_not_reported_missing(tmp_path, capsys):
    j, t = tmp_path / "h.json", tmp_path / "s.tsv"
    write_json(j, [{"permanentLocationId": LOC,
                    "formerIds": ["b1", "b2", "i1"]}])
    write_tsv(t, [["b1;b2", "i1", "xx"]])
    mt.main(["--json", str(j), "--tsv", str(t), "--no-map",
             "--location-uuid", LOC, "--out-dir", str(tmp_path / "o")])
    assert "not found in TSV     : 0" in capsys.readouterr().out
