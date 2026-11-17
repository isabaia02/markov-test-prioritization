"""
run_benchmark.py - Percorre a árvore completa do benchmark e aplica
H1 e H2 a todas as MEFs (ou apenas a uma, ou a um subconjunto).

Estrutura esperada:
    data/mefs-markov/                 <- --root
        4-4-4/                        <- estrutura (estados-entradas-saídas)
            1/                        <- instância (uma MEF)
                fsm1.txt              (opcional: validação cruzada)
                tshnina.txt  tshsi.txt  tsp3.txt  tsw.txt  tsspy.txt   (suítes)
                HInput.txt  logH.txt  size.txt                          (ignorados)
                markovmodels/
                    markov-model-1.yaml ... markov-model-100.yaml
            2/ ... 100/
        6-4-4/ ...
        ...

Uma "instância" é qualquer pasta que contenha uma subpasta "markovmodels".

Para cada (modelo, método) é gerado 1 arquivo de saída, gravado em
<output-root>/<estrutura>/<instância>/<modelo>/ (padrão: results/).
Saídas que já existem são puladas, então o script pode ser interrompido
(Ctrl+C) e rodado de novo sem refazer o que já foi feito.

Exemplos (a partir da raiz do projeto)
--------------------------------------
Tudo (todas as estruturas, instâncias, modelos e métodos):
    python src/run_benchmark.py

Só uma MEF (4-4-4/1), todos os 100 modelos, só método H:
    python src/run_benchmark.py --structure 4-4-4 --instance 1 --method H

Só um modelo específico de uma MEF:
    python src/run_benchmark.py --structure 4-4-4 --instance 1 \
        --model markov-model-1.yaml

Uma estrutura inteira (as 100 instâncias de 6-4-4):
    python src/run_benchmark.py --structure 6-4-4

Ver o que seria processado, sem rodar nada:
    python src/run_benchmark.py --list

Usar o exemplo do repositório (sem o dataset completo):
    python src/run_benchmark.py --root examples
"""

import argparse
import os
import re
import sys
import time

from process_instance import (
    DEFAULT_DATA_ROOT,
    DEFAULT_RESULTS_ROOT,
    process_instance,
)
from suite_io import SUITE_FILE_BY_METHOD


def _sort_key(name):
    """Ordena '4-4-4' < '6-4-4' < '10-4-4' e '2' < '10' (numericamente)."""
    parts = re.split(r"(\d+)", name)
    return [int(p) if p.isdigit() else p for p in parts]


def _subfolders(path):
    return sorted(
        (d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))),
        key=_sort_key,
    )


def discover_instances(root, structure=None, instance=None):
    """Devolve lista de (estrutura, instância, caminho) para cada pasta que
    contém 'markovmodels/'. Filtra por estrutura e/ou instância se pedido."""
    if not os.path.isdir(root):
        raise FileNotFoundError(f"Pasta raiz não encontrada: {root}")

    structures = _subfolders(root)
    if structure:
        if structure not in structures:
            raise FileNotFoundError(
                f"Estrutura '{structure}' não encontrada em {root}. "
                f"Disponíveis: {structures}"
            )
        structures = [structure]

    found = []
    for struct in structures:
        struct_path = os.path.join(root, struct)
        for inst in _subfolders(struct_path):
            if instance and inst != str(instance):
                continue
            inst_path = os.path.join(struct_path, inst)
            if os.path.isdir(os.path.join(inst_path, "markovmodels")):
                found.append((struct, inst, inst_path))

    if instance and not found:
        raise FileNotFoundError(
            f"Instância '{instance}' (com markovmodels/) não encontrada "
            f"{'em ' + structure if structure else 'em nenhuma estrutura'}."
        )
    return found


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, sec = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}min {sec}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}min"


def main():
    ap = argparse.ArgumentParser(
        description="Aplica H1 e H2 a todas as MEFs do benchmark (ou a um subconjunto)."
    )
    ap.add_argument("--root", default=DEFAULT_DATA_ROOT,
                    help="Pasta raiz do benchmark (padrão: data/mefs-markov).")
    ap.add_argument("--structure", default=None,
                    help="Processa só esta estrutura (ex.: 4-4-4).")
    ap.add_argument("--instance", default=None,
                    help="Processa só esta instância (ex.: 1). Combine com "
                         "--structure para escolher exatamente uma MEF.")
    ap.add_argument("--model", default=None,
                    help="Processa só este arquivo de markovmodels/ "
                         "(ex.: markov-model-1.yaml).")
    ap.add_argument("--method", default="all",
                    choices=["H", "HSI", "P", "W", "PY", "all"],
                    help="Suíte de teste a usar (padrão: todas as disponíveis).")
    ap.add_argument("--output-root", default=DEFAULT_RESULTS_ROOT,
                    help="Grava as saídas em <output-root>/<estrutura>/<instância>/ "
                         "(padrão: results/).")
    ap.add_argument("--overwrite", action="store_true",
                    help="Reprocessa mesmo que a saída já exista.")
    ap.add_argument("--verbose", action="store_true",
                    help="Imprime uma linha por arquivo (muito longo no benchmark inteiro).")
    ap.add_argument("--list", action="store_true",
                    help="Só lista as instâncias que seriam processadas e sai.")
    args = ap.parse_args()

    try:
        instances = discover_instances(args.root, args.structure, args.instance)
    except FileNotFoundError as e:
        print(str(e))
        sys.exit(1)

    if not instances:
        print(f"Nenhuma instância (pasta com markovmodels/) encontrada em {args.root}.")
        sys.exit(1)

    if args.list:
        print(f"{len(instances)} instância(s) encontrada(s):")
        for struct, inst, path in instances:
            print(f"  {struct}/{inst}   ({path})")
        return

    print(f"{len(instances)} instância(s) a processar (método={args.method}).")

    total_start = time.perf_counter()
    totals = {"done": 0, "skipped": 0, "errors": 0}
    all_error_messages = []
    instances_with_missing_suites = []

    for i, (struct, inst, path) in enumerate(instances, start=1):
        output_dir = os.path.join(args.output_root, struct, inst)

        t0 = time.perf_counter()
        r = process_instance(
            instance_dir=path, model=args.model, method=args.method,
            output_dir=output_dir, overwrite=args.overwrite, log=args.verbose,
        )
        dt = time.perf_counter() - t0

        for k in totals:
            totals[k] += r[k]
        all_error_messages.extend(r.get("error_messages", []))
        if r.get("missing_suites"):
            instances_with_missing_suites.append((struct, inst, r["missing_suites"]))

        elapsed = time.perf_counter() - total_start
        print(f"[{i}/{len(instances)}] {struct}/{inst}: "
              f"{r['done']} feitos, {r['skipped']} pulados, {r['errors']} erros "
              f"({format_duration(dt)}; total decorrido {format_duration(elapsed)})")

    print()
    print(f"RESUMO FINAL: {totals['done']} gerado(s), {totals['skipped']} pulado(s) "
          f"(já existiam), {totals['errors']} com erro "
          f"em {format_duration(time.perf_counter() - total_start)}.")

    if instances_with_missing_suites:
        print(f"ATENÇÃO: {len(instances_with_missing_suites)} instância(s) sem alguma "
              f"suíte documentada no README (processadas apenas com as suítes existentes):")
        for struct, inst, missing in instances_with_missing_suites[:10]:
            print(f"  - {struct}/{inst}: sem "
                  f"{', '.join(SUITE_FILE_BY_METHOD[m] for m in missing)}")
        if len(instances_with_missing_suites) > 10:
            print(f"  ... e mais {len(instances_with_missing_suites) - 10}")

    if all_error_messages:
        os.makedirs(args.output_root, exist_ok=True)
        log_path = os.path.join(args.output_root, "benchmark_errors.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(all_error_messages) + "\n")
        print(f"{len(all_error_messages)} erro(s) registrado(s) em {log_path}. "
              f"Primeiros:")
        for msg in all_error_messages[:5]:
            print(f"  - {msg}")
        sys.exit(2)


if __name__ == "__main__":
    main()
