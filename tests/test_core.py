"""Testes de h1_h2_core com a cadeia de 2 estados de conftest.TOY_YAML."""

import pytest

from fsm_model_io import load_fsm
from h1_h2_core import (
    build_state_list,
    compute_h1,
    compute_h2,
    compute_stationary_distribution,
    prioritize,
)
from suite_io import load_test_cases


def test_stationary_distribution_matches_hand_calculation(toy_model_path):
    fsm = load_fsm(toy_model_path)
    pi, warnings = compute_stationary_distribution(fsm)
    assert pi["A"] == pytest.approx(0.4)
    assert pi["B"] == pytest.approx(0.6)
    assert sum(pi.values()) == pytest.approx(1.0)
    assert warnings == []


def test_h1_is_product_of_transition_probabilities(toy_model_path):
    fsm = load_fsm(toy_model_path)
    # entrada "01": A -0-> A (t1, 0.25), A -1-> B (t2, 0.75)
    assert compute_h1(["t1", "t2"], fsm) == pytest.approx(0.1875)


def test_h2_is_product_of_stationary_probabilities_including_repeats(toy_model_path):
    fsm = load_fsm(toy_model_path)
    pi, _ = compute_stationary_distribution(fsm)
    # estados visitados por "01": A, A, B -> 0.4 * 0.4 * 0.6
    assert compute_h2(["A", "A", "B"], pi) == pytest.approx(0.096)


def _cases(tmp_path, fsm, lines):
    suite = tmp_path / "suite.txt"
    suite.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return load_test_cases(str(suite), fsm)


def test_prioritize_ranks_in_descending_score(toy_model_path, tmp_path):
    fsm = load_fsm(toy_model_path)
    pi, _ = compute_stationary_distribution(fsm)
    cases = _cases(tmp_path, fsm, ["01", "1", "11"])
    results, h1_time, h2_time = prioritize(cases, fsm, pi)

    assert [r.score_h1 for r in results] == pytest.approx([0.1875, 0.75, 0.375])
    assert [r.score_h2 for r in results] == pytest.approx([0.096, 0.24, 0.144])
    assert [r.rank_h1 for r in results] == [3, 1, 2]
    assert [r.rank_h2 for r in results] == [3, 1, 2]
    assert h1_time >= 0 and h2_time >= 0


def test_ties_keep_original_suite_order(toy_model_path, tmp_path):
    fsm = load_fsm(toy_model_path)
    pi, _ = compute_stationary_distribution(fsm)
    cases = _cases(tmp_path, fsm, ["1", "1", "1"])
    results, _, _ = prioritize(cases, fsm, pi)
    assert [r.rank_h1 for r in results] == [1, 2, 3]
    assert [r.rank_h2 for r in results] == [1, 2, 3]


def test_state_without_exit_gets_artificial_transition_back_to_initial(write_yaml):
    path = write_yaml("""\
        states:
          - A
          - B
        initial_state: A
        final_states:
          - B
        transitions:
          - A,0,0,B,1.0
    """)
    fsm = load_fsm(path)
    assert build_state_list(fsm) == ["A", "B"]
    pi, warnings = compute_stationary_distribution(fsm)
    assert pi["A"] == pytest.approx(0.5)
    assert pi["B"] == pytest.approx(0.5)
    assert len(warnings) == 1 and "artificial" in warnings[0]
