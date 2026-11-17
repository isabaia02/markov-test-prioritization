"""
fsm_model_io.py - Leitura e validação de arquivos de entrada contendo uma MEF
probabilística (FSM, do inglês finite state machine, com probabilidades nas
transições; equivale a uma Cadeia de Markov em Tempo Discreto).

Formato esperado do arquivo (texto simples, com sintaxe YAML):
    states:
      - <estado>
      - <estado>
      ...
    initial_state: <estado>
    final_states:
      - <estado>
      ...
    transition_matrix:            # opcional - usado só para conferência
      - <p_estado1->1>,<p_estado1->2>,...
      ...
    transitions:
      - <origem>,<entrada>,<saída>,<destino>,<probabilidade>
      ...

Cada item de "transitions" descreve uma transição da MEF. O formato com 5
campos (origem, entrada, saída, destino, probabilidade) segue a definição
formal de MEF usada no projeto (fz = função de saída, fs = função de
próximo estado). Também é aceito um formato simplificado com 3 campos
(origem, destino, probabilidade), para arquivos que não detalham
entrada/saída.

A lista "transitions" é tratada como a fonte de verdade dos cálculos,
pois é a única que garante, por construção, que a soma das probabilidades
de saída de cada estado seja 1,00. A seção "transition_matrix", quando
presente, é usada apenas como conferência: se divergir do que "transitions"
produz, um aviso é gerado (e o valor de "transitions" prevalece).
"""

from dataclasses import dataclass, field

import yaml


@dataclass
class FSM:
    states: list
    initial_state: str
    final_states: set
    # id -> {"source", "target", "probability", "input", "output"}
    transitions: dict
    warnings: list = field(default_factory=list)


def load_fsm(file_path):
    """Lê e valida um arquivo de MEF, devolvendo um objeto FSM."""
    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Arquivo '{file_path}' não contém um mapeamento YAML válido.")

    required_fields = ["states", "initial_state", "final_states", "transitions"]
    missing = [c for c in required_fields if c not in data]
    if missing:
        raise ValueError(
            f"Arquivo '{file_path}' não possui os campos obrigatórios: {missing}"
        )

    states = [str(s) for s in data["states"]]
    initial_state = str(data["initial_state"])
    final_states = {str(s) for s in data["final_states"]}

    transitions = _parse_transitions(data["transitions"])
    warnings = _validate(data, states, transitions)

    return FSM(states, initial_state, final_states, transitions, warnings)


def _parse_transitions(transition_lines):
    transitions = {}
    for idx, line in enumerate(transition_lines, start=1):
        fields = [c.strip() for c in str(line).split(",")]

        if len(fields) == 5:
            source, input_symbol, output_symbol, target, prob = fields
        elif len(fields) == 3:
            source, target, prob = fields
            input_symbol = output_symbol = None
        else:
            raise ValueError(
                f"Transição com formato inesperado ({len(fields)} campos): "
                f"'{line}'. Esperados 3 campos (origem,destino,probabilidade) "
                f"ou 5 campos (origem,entrada,saída,destino,probabilidade)."
            )

        transitions[f"t{idx}"] = {
            "source": source,
            "target": target,
            "probability": float(prob),
            "input": input_symbol,
            "output": output_symbol,
        }
    return transitions


def _validate(data, states, transitions):
    """Roda verificações de consistência e devolve a lista de avisos
    (não interrompe a execução - apenas alerta)."""
    warnings = []

    # 1) soma das probabilidades de saída por estado, a partir de 'transitions'.
    sum_by_state = {s: 0.0 for s in states}
    for t in transitions.values():
        if t["source"] in sum_by_state:
            sum_by_state[t["source"]] += t["probability"]

    for state, total in sum_by_state.items():
        if total == 0.0:
            continue  # sem transição de saída - tratado à parte no cálculo de pi
        if abs(total - 1.0) > 1e-6:
            warnings.append(
                f"[transitions] a soma das probabilidades de saída do estado "
                f"'{state}' é {total:.4f}, não 1,0000."
            )

    # 2) conferência opcional com 'transition_matrix', se presente no arquivo.
    #    A ordem de linhas/colunas da matriz segue a ordem declarada em 'states'.
    given_matrix = data.get("transition_matrix")
    if given_matrix:
        aggregated = {}
        for t in transitions.values():
            key = (t["source"], t["target"])
            aggregated[key] = aggregated.get(key, 0.0) + t["probability"]

        for i, source in enumerate(states):
            values = [float(v) for v in str(given_matrix[i]).split(",")]
            for j, target in enumerate(states):
                file_value = values[j]
                computed_value = aggregated.get((source, target), 0.0)
                if abs(file_value - computed_value) > 1e-6:
                    warnings.append(
                        f"[transition_matrix] diverge de 'transitions' em "
                        f"{source}->{target}: a matriz diz {file_value:.4f}, "
                        f"a soma das transições diz {computed_value:.4f} "
                        f"(prevalece o valor de 'transitions')."
                    )

    return warnings


def print_fsm(fsm):
    print(f"Estados: {fsm.states}")
    print(f"Estado inicial: {fsm.initial_state}")
    print(f"Estados finais: {sorted(fsm.final_states)}")
    print(f"Quantidade de transições: {len(fsm.transitions)}")
    print()
    for tid, t in fsm.transitions.items():
        label = ""
        if t["input"] is not None:
            label = f"  [entrada={t['input']}, saída={t['output']}]"
        print(f"  {tid}: {t['source']} -> {t['target']}  "
              f"p={t['probability']:.4f}{label}")

    if fsm.warnings:
        print()
        print("AVISOS DE VALIDAÇÃO:")
        for warning in fsm.warnings:
            print(f"  - {warning}")
