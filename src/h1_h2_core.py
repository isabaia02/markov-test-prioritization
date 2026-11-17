"""
h1_h2_core.py - Núcleo de cálculo das heurísticas H1 e H2, independente de
qual MEF/arquivo de entrada está sendo usado.

H1(CT) = produto das probabilidades das TRANSIÇÕES percorridas.
H2(CT) = produto das probabilidades de ESTADO ESTACIONÁRIO (pi) dos
         ESTADOS visitados (incluindo repetições).

Para calcular pi, a cadeia precisa ser ergódica. Estados sem nenhuma
transição de saída (ex.: um estado final absorvente) recebem uma
transição artificial de volta ao estado inicial, com probabilidade 1.0,
usada somente para esse cálculo (ver build_transition_matrix).
"""

import time
from dataclasses import dataclass

import numpy as np


def build_state_list(fsm):
    states = set(fsm.states)
    for t in fsm.transitions.values():
        states.add(t["source"])
        states.add(t["target"])
    return sorted(states)


def build_transition_matrix(fsm, states):
    n = len(states)
    index = {state: i for i, state in enumerate(states)}
    P = np.zeros((n, n))

    for t in fsm.transitions.values():
        i = index[t["source"]]
        j = index[t["target"]]
        P[i][j] += t["probability"]

    states_without_exit = []
    for state in states:
        i = index[state]
        if P[i].sum() == 0:
            j = index[fsm.initial_state]
            P[i][j] = 1.0
            states_without_exit.append(state)

    return P, index, states_without_exit


def compute_stationary_distribution(fsm):
    """Devolve (pi, warnings) onde pi é um dict estado -> probabilidade."""
    states = build_state_list(fsm)
    P, index, states_without_exit = build_transition_matrix(fsm, states)

    n = len(states)
    A = P.T - np.eye(n)
    A[-1, :] = 1.0
    b = np.zeros(n)
    b[-1] = 1.0
    pi_vector = np.linalg.solve(A, b)

    warnings = []
    if states_without_exit:
        warnings.append(
            "Transição artificial adicionada (só para o cálculo de pi) dos "
            f"estados {states_without_exit} de volta a '{fsm.initial_state}', "
            "pois não possuem transição de saída declarada."
        )

    return {state: pi_vector[i] for i, state in enumerate(states)}, warnings


def compute_h1(transition_sequence, fsm):
    score = 1.0
    for tid in transition_sequence:
        score *= fsm.transitions[tid]["probability"]
    return score


def compute_h2(state_sequence, pi):
    score = 1.0
    for state in state_sequence:
        score *= pi[state]
    return score


@dataclass
class CaseResult:
    id: str
    input_sequence: str
    transition_sequence: list
    state_sequence: list
    score_h1: float = 0.0
    score_h2: float = 0.0
    rank_h1: int = 0
    rank_h2: int = 0


def prioritize(test_cases, fsm, pi):
    """test_cases: lista de objetos com .id, .input_sequence,
    .transition_sequence, .state_sequence (ver suite_io.TestCase).

    Devolve (results, h1_time, h2_time). Os tempos (segundos) cobrem,
    cada um, o cálculo das pontuações + a ordenação da respectiva heurística.
    O cálculo de pi NÃO está incluído em h2_time (é feito antes, pelo chamador).

    Em caso de empate, a ordenação (estável) preserva a ordem original da suíte.
    """
    results = [
        CaseResult(
            id=c.id,
            input_sequence=c.input_sequence,
            transition_sequence=c.transition_sequence,
            state_sequence=c.state_sequence,
        )
        for c in test_cases
    ]

    start = time.perf_counter()
    for r in results:
        r.score_h1 = compute_h1(r.transition_sequence, fsm)
    for pos, r in enumerate(sorted(results, key=lambda r: r.score_h1, reverse=True), start=1):
        r.rank_h1 = pos
    h1_time = time.perf_counter() - start

    start = time.perf_counter()
    for r in results:
        r.score_h2 = compute_h2(r.state_sequence, pi)
    for pos, r in enumerate(sorted(results, key=lambda r: r.score_h2, reverse=True), start=1):
        r.rank_h2 = pos
    h2_time = time.perf_counter() - start

    return results, h1_time, h2_time
