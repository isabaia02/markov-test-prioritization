"""
process_instance.py - Aplica H1 e H2 aos modelos de Markov de UMA instância
(pasta de MEF) do benchmark, ex.: data/mefs-markov/4-4-4/1, usando os casos
de teste de uma (ou de todas) as suítes disponíveis (H/HSI/P/W/PY).

Para rodar o benchmark inteiro (várias estruturas e instâncias), use
run_benchmark.py, que reaproveita a função process_instance() daqui.

Estrutura de pasta esperada (conforme o README do benchmark):
    <instância>/
        fsm1.txt            (opcional - usado só para validação cruzada)
        tshnina.txt         (suíte do método H)
        tshsi.txt           (suíte do método HSI)
        tsp3.txt            (suíte do método P)
        tsw.txt             (suíte do método W)
        tsspy.txt           (suíte extra - método PY, fora do README oficial)
        HInput.txt, logH.txt, size.txt   (não são lidos)
        markovmodels/
            markov-model-1.yaml
            markov-model-2.yaml
            ...

Cada combinação (modelo, método) gera exatamente 1 arquivo de saída, nomeado
"<nome-do-modelo>_<MÉTODO>.csv", dentro de uma subpasta com o nome do modelo.
Por padrão, a saída vai para results/<estrutura>/<instância>/ (fora do dataset).

Exemplos de uso (a partir da raiz do projeto)
---------------------------------------------
Um modelo específico, um método:
    python src/process_instance.py --instance-dir data/mefs-markov/4-4-4/1 \
        --model markov-model-1.yaml --method H

Todos os modelos, método HSI:
    python src/process_instance.py --instance-dir data/mefs-markov/4-4-4/1 --method HSI

Todos os modelos, todos os métodos disponíveis na pasta:
    python src/process_instance.py --instance-dir data/mefs-markov/4-4-4/1 --method all

Saídas que já existem são PULADAS automaticamente (não são reprocessadas).
Use --overwrite para forçar o reprocessamento.
"""

import argparse
import csv
import glob
import os
import re
import sys
import time

from fsm_model_io import load_fsm
from plain_fsm_io import load_kiss_fsm, validate_against_fsm
from suite_io import SUITE_FILE_BY_METHOD, load_test_cases
from h1_h2_core import compute_stationary_distribution, prioritize

# Raiz do projeto e pastas padrão, independentes do diretório de onde o script roda.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATA_ROOT = os.path.join(PROJECT_ROOT, "data", "mefs-markov")
DEFAULT_RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results")

DOCUMENTED_METHODS = ["H", "HSI", "P", "W"]

CSV_FIELDS = [
    "model_file", "suite_method", "suite_file",
    "processing_time_s", "h1_time_s", "h2_time_s",
    "id", "input_sequence", "transition_sequence", "state_sequence",
    "score_h1", "rank_h1", "score_h2", "rank_h2", "same_rank",
]


def format_decimal(value):
    """Formata valores decimais da saída com duas casas."""
    return f"{value:.2f}"


def format_time(value):
    """Tempos em segundos com 9 casas (nanossegundos), para não virarem 0.00."""
    return f"{value:.9f}"


def format_score(value):
    """Evita que pontuações pequenas e não nulas sejam exibidas como zero."""
    if value != 0 and round(float(value), 2) == 0:
        return f"{value:.2e}"
    return format_decimal(value)


def default_output_dir(instance_dir, results_root=DEFAULT_RESULTS_ROOT):
    """results/<estrutura>/<instância>, inferido dos dois últimos componentes
    do caminho da instância (ex.: .../4-4-4/1 -> results/4-4-4/1)."""
    instance_dir = os.path.abspath(instance_dir)
    structure = os.path.basename(os.path.dirname(instance_dir))
    instance = os.path.basename(instance_dir)
    return os.path.join(results_root, structure, instance)


def build_output(model_name, method, suite_file, elapsed_s, results,
                 h1_time_s, h2_time_s, fsm_warnings, pi_warnings, cross_warnings):
    cases = []
    for r in results:
        cases.append({
            "id": r.id,
            "input_sequence": r.input_sequence,
            "transition_sequence": r.transition_sequence,
            "state_sequence": r.state_sequence,
            "score_h1": r.score_h1,
            "rank_h1": r.rank_h1,
            "score_h2": r.score_h2,
            "rank_h2": r.rank_h2,
            "same_rank": r.rank_h1 == r.rank_h2,
        })

    return {
        "model_file": model_name,
        "suite_method": method,
        "suite_file": suite_file,
        "processing_time_s": elapsed_s,
        "h1_time_s": h1_time_s,
        "h2_time_s": h2_time_s,
        "test_case_count": len(cases),
        "fsm_warnings": fsm_warnings,
        "stationary_distribution_warnings": pi_warnings,
        "fsm1_cross_validation_warnings": cross_warnings,
        "test_cases": cases,
    }


def write_csv(output, path):
    fixed_columns = {
        "model_file": output["model_file"],
        "suite_method": output["suite_method"],
        "suite_file": output["suite_file"],
        "processing_time_s": format_time(output["processing_time_s"]),
        "h1_time_s": format_time(output["h1_time_s"]),
        "h2_time_s": format_time(output["h2_time_s"]),
    }
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for case in output["test_cases"]:
            row = dict(fixed_columns)
            row.update({
                "id": case["id"],
                "input_sequence": case["input_sequence"],
                "transition_sequence": "-".join(case["transition_sequence"]),
                "state_sequence": "-".join(case["state_sequence"]),
                "score_h1": format_score(case["score_h1"]),
                "rank_h1": case["rank_h1"],
                "score_h2": format_score(case["score_h2"]),
                "rank_h2": case["rank_h2"],
                "same_rank": case["same_rank"],
            })
            w.writerow(row)


def process_one(model_path, suite_path, method, fsm1_path=None):
    """Processa 1 (modelo, método) e devolve o dicionário de saída pronto."""
    start = time.perf_counter()

    fsm = load_fsm(model_path)
    cases = load_test_cases(suite_path, fsm)
    pi_start = time.perf_counter()
    pi, pi_warnings = compute_stationary_distribution(fsm)
    pi_time = time.perf_counter() - pi_start
    results, h1_time, h2_time = prioritize(cases, fsm, pi)
    # pi só é usado por H2, então seu custo entra no tempo de H2.
    h2_time += pi_time

    cross_warnings = []
    if fsm1_path and os.path.isfile(fsm1_path):
        plain_fsm = load_kiss_fsm(fsm1_path)
        cross_warnings = validate_against_fsm(plain_fsm, fsm)

    elapsed = time.perf_counter() - start

    return build_output(
        model_name=os.path.basename(model_path),
        method=method,
        suite_file=os.path.basename(suite_path),
        elapsed_s=elapsed,
        results=results,
        h1_time_s=h1_time,
        h2_time_s=h2_time,
        fsm_warnings=fsm.warnings,
        pi_warnings=pi_warnings,
        cross_warnings=cross_warnings,
    )


def available_methods(instance_dir):
    available = {}
    for method, file_name in SUITE_FILE_BY_METHOD.items():
        path = os.path.join(instance_dir, file_name)
        if os.path.isfile(path):
            available[method] = path
    return available


def _numeric_key(path):
    name = os.path.basename(path)
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", name)]


def list_models(instance_dir, specific_model):
    models_dir = os.path.join(instance_dir, "markovmodels")
    if specific_model:
        path = os.path.join(models_dir, specific_model)
        if not os.path.isfile(path):
            # também aceita caminho absoluto/relativo direto
            if os.path.isfile(specific_model):
                path = specific_model
            else:
                raise FileNotFoundError(f"Modelo não encontrado: {path}")
        return [path]

    candidates = glob.glob(os.path.join(models_dir, "*.yaml")) \
        + glob.glob(os.path.join(models_dir, "*.yml"))
    if not candidates:
        raise FileNotFoundError(
            f"Nenhum arquivo .yaml/.yml encontrado em {models_dir}"
        )
    # ordem numérica (markov-model-2 antes de markov-model-10)
    return sorted(candidates, key=_numeric_key)


def process_instance(instance_dir, model=None, method="all",
                     output_dir=None, overwrite=False, log=True):
    """Processa UMA instância (ex.: data/mefs-markov/4-4-4/1).

    Devolve dict: {"done", "skipped", "errors", "total", "error_messages",
    "missing_suites"}. Usada tanto pela CLI deste arquivo quanto pelo varredor
    de benchmark inteiro (run_benchmark.py).
    """
    output_dir = output_dir or default_output_dir(instance_dir)
    os.makedirs(output_dir, exist_ok=True)

    fsm1_path = os.path.join(instance_dir, "fsm1.txt")

    methods = available_methods(instance_dir)
    if not methods:
        msg = f"{instance_dir}: nenhuma suíte de teste conhecida encontrada " \
              f"(esperava um de: {list(SUITE_FILE_BY_METHOD.values())})"
        if log:
            print(msg)
        return {"done": 0, "skipped": 0, "errors": 1, "total": 0,
                "error_messages": [msg], "missing_suites": []}

    missing_suites = []
    if method == "all":
        missing_suites = [m for m in DOCUMENTED_METHODS if m not in methods]
        if missing_suites and log:
            print(f"  [AVISO]   {instance_dir}: suíte(s) ausente(s): "
                  f"{[SUITE_FILE_BY_METHOD[m] for m in missing_suites]}")

    if method != "all":
        if method not in methods:
            msg = f"{instance_dir}: método '{method}' pedido, mas " \
                  f"'{SUITE_FILE_BY_METHOD[method]}' não existe"
            if log:
                print(msg)
            return {"done": 0, "skipped": 0, "errors": 1, "total": 0,
                    "error_messages": [msg], "missing_suites": []}
        methods = {method: methods[method]}

    try:
        models = list_models(instance_dir, model)
    except FileNotFoundError as e:
        if log:
            print(str(e))
        return {"done": 0, "skipped": 0, "errors": 1, "total": 0,
                "error_messages": [f"{instance_dir}: {e}"], "missing_suites": []}

    total = len(models) * len(methods)
    done = skipped = errors = 0
    error_messages = []

    if log:
        print(f"[{instance_dir}] {len(models)} modelo(s) x {len(methods)} método(s) "
              f"= {total} combinação(ões) a considerar.")

    for model_path in models:
        base_name = os.path.splitext(os.path.basename(model_path))[0]

        for met, suite_path in methods.items():
            model_output_dir = os.path.join(output_dir, base_name)
            os.makedirs(model_output_dir, exist_ok=True)
            output_name = f"{base_name}_{met}.csv"
            output_path = os.path.join(model_output_dir, output_name)

            if os.path.isfile(output_path) and not overwrite:
                skipped += 1
                if log:
                    print(f"  [PULADO]  {output_name} (já existe)")
                continue

            try:
                output = process_one(model_path, suite_path, met, fsm1_path)
            except Exception as e:
                errors += 1
                error_messages.append(f"{model_path} / {met}: {e}")
                if log:
                    print(f"  [ERRO]    {os.path.basename(model_path)} / {met}: {e}")
                continue

            # escrita atômica: uma execução interrompida não deixa CSV truncado,
            # que seria pulado (como "já existe") nas execuções seguintes.
            tmp_path = output_path + ".tmp"
            write_csv(output, tmp_path)
            os.replace(tmp_path, output_path)

            done += 1
            if log:
                n_warnings = (len(output["fsm_warnings"])
                              + len(output["stationary_distribution_warnings"])
                              + len(output["fsm1_cross_validation_warnings"]))
                warning_note = f", {n_warnings} aviso(s)" if n_warnings else ""
                print(f"  [FEITO]   {output_name}  "
                      f"({output['test_case_count']} casos, "
                      f"{output['processing_time_s']*1000:.2f} ms{warning_note})")

    return {"done": done, "skipped": skipped, "errors": errors, "total": total,
            "error_messages": error_messages, "missing_suites": missing_suites}


def main():
    ap = argparse.ArgumentParser(
        description="Aplica H1 e H2 aos modelos de Markov de UMA instância do benchmark "
                    "(ex.: data/mefs-markov/4-4-4/1). "
                    "Para rodar o benchmark inteiro, use run_benchmark.py."
    )
    ap.add_argument("--instance-dir", required=True,
                    help="Pasta da instância de MEF (contendo as suítes e markovmodels/).")
    ap.add_argument("--model", default=None,
                    help="Nome de um arquivo específico em markovmodels/ "
                         "(ex.: markov-model-1.yaml). Se omitido, roda todos.")
    ap.add_argument("--method", default="all",
                    choices=["H", "HSI", "P", "W", "PY", "all"],
                    help="Qual suíte de teste usar (padrão: todas as disponíveis).")
    ap.add_argument("--output-dir", default=None,
                    help="Pasta onde gravar as saídas "
                         "(padrão: results/<estrutura>/<instância>).")
    ap.add_argument("--overwrite", action="store_true",
                    help="Reprocessa mesmo que o arquivo de saída já exista.")
    args = ap.parse_args()

    r = process_instance(
        instance_dir=args.instance_dir, model=args.model, method=args.method,
        output_dir=args.output_dir, overwrite=args.overwrite, log=True,
    )

    print()
    print(f"Resumo: {r['done']} gerado(s), {r['skipped']} pulado(s) "
          f"(já existiam), {r['errors']} com erro.")
    if r["errors"] and r["total"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
