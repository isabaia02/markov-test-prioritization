"""
suite_io.py - Leitura das suítes de teste do benchmark (arquivos
tshnina.txt, tshsi.txt, tsp3.txt, tsw.txt, tsspy.txt) e reconstrução do
caminho (sequência de transições e de estados) que cada caso de teste
percorre na MEF.

Formato dos arquivos: uma sequência de teste por linha, escrita como uma
string de dígitos sem separador (ex.: "1011"). Cada dígito é um SÍMBOLO
DE ENTRADA (ver fs/fz na definição formal de MEF) a ser aplicado, em
ordem, a partir do estado inicial.

PREMISSA: o README do benchmark não especifica o formato das linhas dessas
suítes. A leitura como "sequência de símbolos de entrada, um dígito por
símbolo" foi inferida e confirmada empiricamente: as sequências dos
arquivos de exemplo foram percorridas com sucesso nas MEFs, sem nenhum par
(estado, entrada) inválido. Ela pressupõe entradas de um único dígito (0-9);
MEFs com 10 ou mais símbolos de entrada exigiriam outro separador, e uma
sequência incompatível com a MEF gera erro em rebuild_path.

Métodos reconhecidos (identificador do método -> nome do arquivo no dataset):
    H   -> tshnina.txt
    HSI -> tshsi.txt
    P   -> tsp3.txt
    W   -> tsw.txt
    PY  -> tsspy.txt (suíte extra, fora da documentação do benchmark)
"""

from dataclasses import dataclass, field

# Os nomes de arquivo são os do dataset (formato externo), por isso não são traduzidos.
SUITE_FILE_BY_METHOD = {
    "H": "tshnina.txt",
    "HSI": "tshsi.txt",
    "P": "tsp3.txt",
    "W": "tsw.txt",
    "PY": "tsspy.txt",
}


@dataclass
class TestCase:
    __test__ = False  # evita que o pytest tente coletar esta classe como teste

    id: str
    input_sequence: str
    transition_sequence: list = field(default_factory=list)
    state_sequence: list = field(default_factory=list)
    output_sequence: list = field(default_factory=list)


def load_suite(file_path):
    """Lê o arquivo e devolve a lista de sequências de entrada (uma string
    de dígitos por linha), na ordem em que aparecem."""
    with open(file_path, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines


def build_input_index(fsm):
    """Índice (origem, entrada) -> id da transição. Construir uma vez por
    MEF e reaproveitar para todas as linhas da suíte (evita refazer este
    índice a cada caso de teste)."""
    index = {}
    for tid, t in fsm.transitions.items():
        if t["input"] is not None:
            index[(t["source"], t["input"])] = tid
    return index


def rebuild_path(input_sequence, fsm, index=None):
    """Caminha pela MEF a partir do estado inicial, aplicando um dígito de
    entrada por vez, e devolve (transition_sequence, state_sequence,
    output_sequence). Lança ValueError se algum dígito não corresponder
    a nenhuma transição válida a partir do estado atual."""
    if index is None:
        index = build_input_index(fsm)

    state = fsm.initial_state
    states = [state]
    traversed_transitions = []
    outputs = []

    for digit in input_sequence:
        key = (state, digit)
        if key not in index:
            raise ValueError(
                f"Sequência '{input_sequence}': não existe transição para "
                f"(estado={state}, entrada={digit}). Isso pode indicar que "
                f"a suíte não usa 1 dígito por símbolo de entrada, ou que o "
                f"arquivo da MEF não é compatível com esta suíte."
            )
        tid = index[key]
        t = fsm.transitions[tid]
        states.append(t["target"])
        traversed_transitions.append(tid)
        outputs.append(t["output"])
        state = t["target"]

    return traversed_transitions, states, outputs


def load_test_cases(suite_path, fsm, id_prefix="CT"):
    """Lê a suíte e devolve uma lista de TestCase, já com o caminho
    (transições/estados/saídas) reconstruído na MEF informada."""
    sequences = load_suite(suite_path)
    index = build_input_index(fsm)
    cases = []
    for idx, seq in enumerate(sequences, start=1):
        transitions, states, outputs = rebuild_path(seq, fsm, index)
        cases.append(TestCase(
            id=f"{id_prefix}{idx:03d}",
            input_sequence=seq,
            transition_sequence=transitions,
            state_sequence=states,
            output_sequence=outputs,
        ))
    return cases
