"""
consolidate_results.py - Junta os tempos H1/H2 de todos os CSVs de
resultados em um único CSV, com 1 linha por (Configuration, FSM ID,
Markov ID, TestSuite).

Estrutura lida (a mesma gerada por run_benchmark.py):
    <results>/<config>/<fsm>/markov-model-<N>/markov-model-<N>_<SUITE>.csv

Saída: Configuration, FSM ID, Markov ID, TestSuite, H1 Runtime, H2 Runtime
(segundos). Padrão: results/runtime_summary.csv.

A execução é incremental: arquivos cuja chave já está no consolidado não são
relidos. Use --rebuild após reprocessar resultados com --overwrite.
CSVs sem as colunas h1_time_s/h2_time_s são ignorados com aviso.

Exemplos (a partir da raiz do projeto):
    python src/consolidate_results.py
    python src/consolidate_results.py --config 4-4-4 6-4-4
    python src/consolidate_results.py --config all --rebuild
"""

import argparse
import os
import re
import sys

import pandas as pd

from process_instance import DEFAULT_RESULTS_ROOT

KEY = ["Configuration", "FSM ID", "Markov ID", "TestSuite"]
COLUMNS = KEY + ["H1 Runtime", "H2 Runtime"]
SOURCE_COLUMNS = ["h1_time_s", "h2_time_s"]
FILE_RE = re.compile(r"^markov-model-(\d+)_([A-Za-z0-9]+)\.csv$")
CONFIG_RE = re.compile(r"^(\d+)-\d+-\d+$")


def list_configurations(results_root, chosen):
    all_configs = sorted(
        (d for d in os.listdir(results_root)
         if CONFIG_RE.match(d) and os.path.isdir(os.path.join(results_root, d))),
        key=lambda d: int(CONFIG_RE.match(d).group(1)),
    )
    if chosen == ["all"]:
        return all_configs
    missing = [c for c in chosen if c not in all_configs]
    if missing:
        sys.exit(f"Configuração(ões) não encontrada(s) em {results_root}: {missing}")
    return [c for c in all_configs if c in chosen]


def list_files(results_root, configs):
    """Gera (chave, caminho) para cada CSV de resultado encontrado."""
    for config in configs:
        config_dir = os.path.join(results_root, config)
        for fsm in os.listdir(config_dir):
            fsm_dir = os.path.join(config_dir, fsm)
            if not (fsm.isdigit() and os.path.isdir(fsm_dir)):
                continue
            for model in os.listdir(fsm_dir):
                model_dir = os.path.join(fsm_dir, model)
                if not os.path.isdir(model_dir):
                    continue
                for name in os.listdir(model_dir):
                    m = FILE_RE.match(name)
                    if m:
                        key = (config, int(fsm), int(m.group(1)), m.group(2))
                        yield key, os.path.join(model_dir, name)


def read_times(path):
    """Devolve (h1, h2) da 1ª linha do CSV, ou None se o formato for
    antigo/ilegível."""
    try:
        df = pd.read_csv(path, usecols=lambda c: c in SOURCE_COLUMNS, nrows=1)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
        return None
    if df.empty or any(c not in df.columns for c in SOURCE_COLUMNS):
        return None
    return float(df["h1_time_s"].iloc[0]), float(df["h2_time_s"].iloc[0])


def sort_rows(df):
    df = df.copy()
    df["_states"] = df["Configuration"].str.split("-").str[0].astype(int)
    df = df.sort_values(["_states", "FSM ID", "Markov ID", "TestSuite"])
    return df.drop(columns="_states").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--results", default=DEFAULT_RESULTS_ROOT,
                    help="Pasta com os resultados gerados (padrão: results/).")
    ap.add_argument("--output", default=None,
                    help="CSV consolidado (padrão: <results>/runtime_summary.csv).")
    ap.add_argument("--config", nargs="+", default=["4-4-4"],
                    help="Configurações a incluir (ex.: 4-4-4 6-4-4) ou 'all'. "
                         "Padrão: 4-4-4")
    ap.add_argument("--rebuild", action="store_true",
                    help="Ignora o consolidado existente e relê todos os CSVs.")
    args = ap.parse_args()

    if not os.path.isdir(args.results):
        sys.exit(f"Pasta de resultados não encontrada: {args.results}")
    output = args.output or os.path.join(args.results, "runtime_summary.csv")

    configs = list_configurations(args.results, args.config)

    existing = pd.DataFrame(columns=COLUMNS)
    if os.path.isfile(output) and not args.rebuild:
        existing = pd.read_csv(output)
        missing = [c for c in COLUMNS if c not in existing.columns]
        if missing:
            sys.exit(f"{output} não tem as colunas esperadas {missing}; "
                     "use --rebuild.")
    already_seen = set(map(tuple, existing[KEY].itertuples(index=False, name=None)))

    new_rows, unreadable_count, unreadable_examples = [], 0, []
    for key, path in list_files(args.results, configs):
        if key in already_seen:
            continue
        times = read_times(path)
        if times is None:
            unreadable_count += 1
            if len(unreadable_examples) < 5:
                unreadable_examples.append(path)
            continue
        new_rows.append((*key, *times))

    if new_rows:
        df = pd.concat([existing, pd.DataFrame(new_rows, columns=COLUMNS)],
                       ignore_index=True)
    else:
        df = existing
    df = sort_rows(df.drop_duplicates(subset=KEY, keep="last")) if len(df) else df
    if len(df):
        for c in ["FSM ID", "Markov ID"]:
            df[c] = df[c].astype(int)
        for c in ["H1 Runtime", "H2 Runtime"]:
            df[c] = df[c].astype(float)

    if new_rows or args.rebuild or not os.path.isfile(output):
        tmp = output + ".tmp"
        df.to_csv(tmp, index=False, float_format="%.9f")
        os.replace(tmp, output)

    print(f"Configurações: {', '.join(configs)}")
    print(f"Linhas novas: {len(new_rows)} | total em {output}: {len(df)}")
    if unreadable_count:
        print(f"AVISO: {unreadable_count} CSV(s) ignorado(s) por não terem as colunas "
              "h1_time_s/h2_time_s ou estarem ilegíveis. "
              "Reprocesse-os com --overwrite. Exemplos:")
        for c in unreadable_examples:
            print(f"  {c}")


if __name__ == "__main__":
    main()
