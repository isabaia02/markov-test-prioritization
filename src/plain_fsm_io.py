"""
plain_fsm_io.py - Leitura do arquivo "fsm1.txt" (MEF pura, sem probabilidades,
no formato kiss usado no benchmark):

    <origem> -- <entrada> / <saída> -> <destino>

Esse arquivo descreve a mesma estrutura (estados, entradas, saídas,
função de próximo estado) que os arquivos markov-model-N.yaml da pasta
markovmodels/ - a diferença é que o fsm1.txt não tem probabilidades.

Ele é usado apenas para VALIDAÇÃO CRUZADA: conferimos se a função de
próximo estado (fs) e de saída (fz) de cada markov-model-N.yaml bate com
o fsm1.txt "oficial" da pasta. Isso ajuda a detectar arquivos de modelo
que, por algum erro de geração, não correspondam de fato à MEF original.
"""

from dataclasses import dataclass


@dataclass
class PlainFSM:
    # transitions[(source, input)] = (target, output)
    transitions: dict


def load_kiss_fsm(file_path):
    transitions = {}
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                left, rest = line.split("--")
                source = left.strip()
                input_output, target = rest.split("->")
                input_symbol, output_symbol = input_output.split("/")
            except ValueError:
                raise ValueError(
                    f"Linha fora do formato esperado "
                    f"'<origem> -- <entrada> / <saída> -> <destino>': '{line}'"
                )
            transitions[(source.strip(), input_symbol.strip())] = (
                target.strip(), output_symbol.strip()
            )
    return PlainFSM(transitions=transitions)


def validate_against_fsm(plain_fsm, fsm):
    """Confere se cada transição do FSM (origem+entrada) leva ao mesmo
    destino e produz a mesma saída que o fsm1.txt. Devolve a lista de
    divergências (vazia se tudo bater)."""
    mismatches = []
    for tid, t in fsm.transitions.items():
        if t["input"] is None:
            continue  # o arquivo da MEF não informa entrada/saída - não dá para cruzar
        key = (t["source"], t["input"])
        if key not in plain_fsm.transitions:
            mismatches.append(
                f"{tid}: par (origem={t['source']}, entrada={t['input']}) "
                f"não existe no fsm1.txt."
            )
            continue
        expected_target, expected_output = plain_fsm.transitions[key]
        if t["target"] != expected_target or t["output"] != expected_output:
            mismatches.append(
                f"{tid}: fsm1.txt diz origem={t['source']}, entrada={t['input']} "
                f"-> destino={expected_target}, saída={expected_output}; "
                f"o modelo diz destino={t['target']}, saída={t['output']}."
            )
    return mismatches
