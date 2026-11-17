"""Testes dos leitores: fsm_model_io, plain_fsm_io e suite_io."""

import pytest

from fsm_model_io import load_fsm
from plain_fsm_io import load_kiss_fsm, validate_against_fsm
from suite_io import (
    SUITE_FILE_BY_METHOD,
    build_input_index,
    load_suite,
    rebuild_path,
)


# ---------- fsm_model_io ----------

def test_load_fsm_parses_five_field_transitions(toy_model_path):
    fsm = load_fsm(toy_model_path)
    assert fsm.states == ["A", "B"]
    assert fsm.initial_state == "A"
    assert fsm.final_states == {"B"}
    assert fsm.transitions["t2"] == {
        "source": "A", "target": "B", "probability": 0.75,
        "input": "1", "output": "1",
    }
    assert fsm.warnings == []


def test_load_fsm_accepts_three_field_transitions(write_yaml):
    path = write_yaml("""\
        states: [A, B]
        initial_state: A
        final_states: [B]
        transitions:
          - A,B,1.0
          - B,A,1.0
    """)
    t = load_fsm(path).transitions["t1"]
    assert (t["input"], t["output"]) == (None, None)
    assert t["target"] == "B"


def test_load_fsm_rejects_missing_fields(write_yaml):
    path = write_yaml("""\
        states: [A]
        initial_state: A
    """)
    with pytest.raises(ValueError, match="campos obrigatórios"):
        load_fsm(path)


def test_load_fsm_rejects_bad_transition_format(write_yaml):
    path = write_yaml("""\
        states: [A]
        initial_state: A
        final_states: [A]
        transitions:
          - A,0,0
          - "A,0,0,A"
    """)
    with pytest.raises(ValueError, match="formato inesperado"):
        load_fsm(path)


def test_warns_when_outgoing_probabilities_do_not_sum_to_one(write_yaml):
    path = write_yaml("""\
        states: [A, B]
        initial_state: A
        final_states: [B]
        transitions:
          - A,0,0,B,0.5
          - B,0,0,A,1.0
    """)
    warnings = load_fsm(path).warnings
    assert len(warnings) == 1 and "'A'" in warnings[0]


def test_warns_when_transition_matrix_diverges_but_transitions_prevail(write_yaml):
    path = write_yaml("""\
        states: [A, B]
        initial_state: A
        final_states: [B]
        transition_matrix:
          - 0.1,0.9
          - 0.5,0.5
        transitions:
          - A,0,0,A,0.25
          - A,1,1,B,0.75
          - B,0,0,A,0.5
          - B,1,1,B,0.5
    """)
    fsm = load_fsm(path)
    assert any("transition_matrix" in w and "A->A" in w for w in fsm.warnings)
    assert fsm.transitions["t1"]["probability"] == 0.25


# ---------- plain_fsm_io ----------

KISS = "A -- 0 / 0 -> A\nA -- 1 / 1 -> B\nB -- 0 / 0 -> A\nB -- 1 / 1 -> B\n"


def test_kiss_matches_model(tmp_path, toy_model_path):
    kiss = tmp_path / "fsm1.txt"
    kiss.write_text(KISS, encoding="utf-8")
    assert validate_against_fsm(load_kiss_fsm(str(kiss)), load_fsm(toy_model_path)) == []


def test_kiss_mismatch_is_reported(tmp_path, toy_model_path):
    kiss = tmp_path / "fsm1.txt"
    kiss.write_text(KISS.replace("A -- 1 / 1 -> B", "A -- 1 / 1 -> A"), encoding="utf-8")
    mismatches = validate_against_fsm(load_kiss_fsm(str(kiss)), load_fsm(toy_model_path))
    assert len(mismatches) == 1 and mismatches[0].startswith("t2:")


def test_kiss_rejects_malformed_line(tmp_path):
    kiss = tmp_path / "fsm1.txt"
    kiss.write_text("isso nao e kiss\n", encoding="utf-8")
    with pytest.raises(ValueError, match="fora do formato"):
        load_kiss_fsm(str(kiss))


# ---------- suite_io ----------

def test_rebuild_path_follows_inputs_from_initial_state(toy_model_path):
    fsm = load_fsm(toy_model_path)
    transitions, states, outputs = rebuild_path("011", fsm)
    assert transitions == ["t1", "t2", "t4"]
    assert states == ["A", "A", "B", "B"]
    assert outputs == ["0", "1", "1"]


def test_rebuild_path_rejects_input_without_transition(toy_model_path):
    fsm = load_fsm(toy_model_path)
    with pytest.raises(ValueError, match="não existe transição"):
        rebuild_path("019", fsm)


def test_build_input_index_ignores_transitions_without_input(write_yaml):
    path = write_yaml("""\
        states: [A, B]
        initial_state: A
        final_states: [B]
        transitions:
          - A,B,1.0
    """)
    assert build_input_index(load_fsm(path)) == {}


def test_load_suite_skips_blank_lines(tmp_path):
    suite = tmp_path / "suite.txt"
    suite.write_text("01\n\n  1  \n", encoding="utf-8")
    assert load_suite(str(suite)) == ["01", "1"]


def test_suite_file_names_follow_the_benchmark():
    assert SUITE_FILE_BY_METHOD == {
        "H": "tshnina.txt", "HSI": "tshsi.txt", "P": "tsp3.txt",
        "W": "tsw.txt", "PY": "tsspy.txt",
    }
