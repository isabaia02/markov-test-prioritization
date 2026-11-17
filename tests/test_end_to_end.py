"""Ponta a ponta sobre examples/ (não depende do dataset completo)."""

import csv
import os
import subprocess
import sys


from conftest import EXAMPLES_ROOT, SRC_DIR
from process_instance import CSV_FIELDS, default_output_dir, process_instance
from run_benchmark import discover_instances

INSTANCE_DIR = os.path.join(EXAMPLES_ROOT, "4-4-4", "1")


def _run(script, *args):
    return subprocess.run(
        [sys.executable, os.path.join(SRC_DIR, script), *args],
        capture_output=True, text=True,
    )


def _read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_discover_instances_finds_example():
    assert discover_instances(EXAMPLES_ROOT) == [("4-4-4", "1", INSTANCE_DIR)]


def test_default_output_dir_uses_structure_and_instance():
    out = default_output_dir(INSTANCE_DIR, results_root="/r")
    assert out == os.path.join("/r", "4-4-4", "1")


def test_process_instance_generates_one_csv_per_model_and_method(tmp_path):
    out = tmp_path / "out"
    r = process_instance(INSTANCE_DIR, output_dir=str(out), log=False)
    assert (r["done"], r["skipped"], r["errors"], r["total"]) == (15, 0, 0, 15)

    files = sorted(p.name for p in out.glob("markov-model-*/*.csv"))
    assert len(files) == 15
    assert "markov-model-1_H.csv" in files and "markov-model-3_PY.csv" in files

    rows = _read(out / "markov-model-1" / "markov-model-1_HSI.csv")
    assert list(rows[0].keys()) == CSV_FIELDS
    n = len(rows)
    assert n == 21  # linhas de examples/4-4-4/1/tshsi.txt
    assert sorted(int(x["rank_h1"]) for x in rows) == list(range(1, n + 1))
    assert sorted(int(x["rank_h2"]) for x in rows) == list(range(1, n + 1))
    assert rows[0]["id"] == "CT001" and rows[0]["suite_method"] == "HSI"


def test_existing_outputs_are_skipped_unless_overwrite(tmp_path):
    out = str(tmp_path / "out")
    process_instance(INSTANCE_DIR, model="markov-model-1.yaml", method="H",
                     output_dir=out, log=False)
    again = process_instance(INSTANCE_DIR, model="markov-model-1.yaml", method="H",
                             output_dir=out, log=False)
    assert (again["done"], again["skipped"]) == (0, 1)
    forced = process_instance(INSTANCE_DIR, model="markov-model-1.yaml", method="H",
                              output_dir=out, overwrite=True, log=False)
    assert (forced["done"], forced["skipped"]) == (1, 0)


def test_missing_model_is_reported_as_error(tmp_path):
    r = process_instance(INSTANCE_DIR, method="PY",
                         model="inexistente.yaml", output_dir=str(tmp_path), log=False)
    assert r["errors"] == 1 and r["done"] == 0


def test_cli_run_benchmark_and_consolidate(tmp_path):
    out = tmp_path / "results"
    p = _run("run_benchmark.py", "--root", EXAMPLES_ROOT, "--output-root", str(out))
    assert p.returncode == 0, p.stdout + p.stderr
    assert len(list(out.glob("4-4-4/1/markov-model-*/*.csv"))) == 15

    p = _run("consolidate_results.py", "--results", str(out), "--config", "4-4-4")
    assert p.returncode == 0, p.stdout + p.stderr
    summary = _read(out / "runtime_summary.csv")
    assert len(summary) == 15
    assert list(summary[0].keys()) == [
        "Configuration", "FSM ID", "Markov ID", "TestSuite", "H1 Runtime", "H2 Runtime",
    ]
    assert {s["TestSuite"] for s in summary} == {"H", "HSI", "P", "W", "PY"}


def test_cli_list_does_not_write_anything(tmp_path):
    out = tmp_path / "results"
    p = _run("run_benchmark.py", "--root", EXAMPLES_ROOT, "--output-root", str(out), "--list")
    assert p.returncode == 0 and "4-4-4/1" in p.stdout
    assert not out.exists()
