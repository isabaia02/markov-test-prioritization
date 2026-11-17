# Protótipo H1/H2 — priorização de casos de teste com cadeias de Markov

Este projeto processa modelos de Máquinas de Estados Finitos (MEFs, em inglês *FSMs*) probabilísticas descritos em YAML e aplica duas heurísticas de priorização de casos de teste:

- **H1**, baseada nas probabilidades das transições percorridas;
- **H2**, baseada nas probabilidades dos estados na distribuição estacionária da cadeia de Markov.

O programa lê as suítes de teste do benchmark (métodos H, HSI, P, W e PY), reconstrói o caminho de cada caso na MEF, calcula as pontuações e posições segundo H1 e H2 e grava os resultados em arquivos CSV, junto com os tempos de execução de cada heurística.

> **Status:** protótipo de pesquisa. **Licença:** a definir (até lá, todos os direitos reservados aos autores).

## Sumário

1. [Estrutura do repositório](#1-estrutura-do-repositório)
2. [Instalação](#2-instalação)
3. [Início rápido (sem o dataset)](#3-início-rápido-sem-o-dataset)
4. [Dados de entrada](#4-dados-de-entrada)
5. [Como executar](#5-como-executar)
6. [Saídas geradas](#6-saídas-geradas)
7. [Consolidação dos tempos](#7-consolidação-dos-tempos)
8. [Como o processamento funciona](#8-como-o-processamento-funciona)
9. [Reprodutibilidade](#9-reprodutibilidade)
10. [Testes](#10-testes)
11. [Premissas e limitações](#11-premissas-e-limitações)

## 1. Estrutura do repositório

```text
markov-prototype/
├── README.md
├── requirements.txt          # dependências de execução
├── requirements-dev.txt      # + pytest
├── pytest.ini
├── src/
│   ├── run_benchmark.py        # ponto de entrada: executa o benchmark (ou parte dele)
│   ├── process_instance.py     # processa uma instância de MEF e grava os CSVs
│   ├── consolidate_results.py  # junta os tempos H1/H2 de todos os CSVs em um só
│   ├── fsm_model_io.py         # lê e valida o modelo probabilístico (YAML)
│   ├── plain_fsm_io.py         # lê fsm1.txt (MEF sem probabilidades) para validação cruzada
│   ├── suite_io.py             # lê as suítes e reconstrói o caminho de cada caso
│   └── h1_h2_core.py           # cálculo de H1, H2, distribuição estacionária e rankings
├── tests/                    # testes automatizados (pytest)
├── examples/4-4-4/1/         # instância mínima (3 modelos) no mesmo formato do benchmark
├── data/
│   ├── README.md             # como obter o dataset completo
│   └── mefs-markov/          # dataset completo (NÃO versionado)
└── results/                  # saídas geradas (NÃO versionadas)
```

| Arquivo | Responsabilidade |
|---|---|
| `run_benchmark.py` | Descobre as instâncias (opcionalmente filtrando por estrutura, instância, modelo ou método), chama o processamento de cada uma, apresenta o resumo e registra erros em `results/benchmark_errors.log`. |
| `process_instance.py` | Processa uma única instância: identifica modelos YAML e suítes disponíveis, chama os módulos de leitura e cálculo e grava um CSV por modelo e método. Também pode ser executado diretamente. |
| `fsm_model_io.py` | Carrega o YAML e o converte em um objeto `FSM`. Lê estados, estado inicial, estados finais e transições com probabilidades; valida a soma das probabilidades e confere `transition_matrix`, quando existe. |
| `plain_fsm_io.py` | Lê o `fsm1.txt` opcional (MEF sem probabilidades) e compara sua estrutura com a do YAML. Serve só como validação cruzada. |
| `suite_io.py` | Mapeia cada método ao arquivo de suíte, lê as sequências de entrada e reconstrói, a partir do estado inicial, as transições e os estados visitados por cada caso. Uma sequência inválida para a MEF gera erro de processamento. |
| `h1_h2_core.py` | Lógica matemática: matriz de transição, distribuição estacionária (H2), pontuações H1 e H2 e posições nos rankings. Não lê nem grava arquivos. |
| `consolidate_results.py` | Reúne os tempos H1/H2 de todos os CSVs gerados em `results/runtime_summary.csv`. |

**Nomenclatura:** os identificadores do código estão em inglês (MEF = *FSM*); comentários e mensagens estão em português. Os nomes de arquivos do dataset (`tshnina.txt`, `markovmodels/`, …) são os do benchmark original e não foram alterados.

## 2. Instalação

Requer Python 3.10 ou superior (testado com Python 3.13). Use um ambiente virtual para não instalar dependências na instalação global:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt   # ou requirements.txt, sem o pytest
```

Ative o ambiente novamente com `source .venv/bin/activate` sempre que abrir um novo terminal. Dependências de execução: `numpy`, `PyYAML` e `pandas` (esta só em `consolidate_results.py`).

## 3. Início rápido (sem o dataset)

O diretório `examples/` contém uma instância do benchmark (estrutura `4-4-4`, instância `1`, modelos 1 a 3) no mesmo formato do dataset completo. A partir da raiz do projeto, com o ambiente ativado:

```bash
python src/run_benchmark.py --root examples      # gera 15 CSVs em results/4-4-4/1/
python src/consolidate_results.py                # gera results/runtime_summary.csv
pytest                                           # roda os testes
```

## 4. Dados de entrada

O dataset completo (`mefs-markov`, cerca de 640 MB de entradas) **não faz parte deste repositório**: é pesado demais para o git e pode ser substituído por novas versões. Ele deve ser colocado em `data/mefs-markov/`. Origem, link de download, estrutura e descrição do benchmark estão em [`data/README.md`](data/README.md).

Formato de uma instância:

```text
data/mefs-markov/4-4-4/1/
├── fsm1.txt            # opcional: validação cruzada
├── tshnina.txt         # suíte H
├── tshsi.txt           # suíte HSI
├── tsp3.txt            # suíte P
├── tsw.txt             # suíte W
├── tsspy.txt           # suíte PY (método extra)
└── markovmodels/
    ├── markov-model-1.yaml
    └── ...
```

Uma instância é identificada por uma pasta que contém `markovmodels/`. As suítes ficam na pasta da instância e são reutilizadas por todos os modelos dela: a estrutura da MEF é a mesma, mas as probabilidades variam entre os YAMLs.

| Arquivo de entrada | Método | Uso |
|---|---|---|
| `tshnina.txt` | `H` | Casos de teste do método H. |
| `tshsi.txt` | `HSI` | Casos de teste do método HSI. |
| `tsp3.txt` | `P` | Casos de teste do método P. |
| `tsw.txt` | `W` | Casos de teste do método W. |
| `tsspy.txt` | `PY` | Suíte adicional, tratada pelo código embora não conste na documentação original do benchmark. |
| `fsm1.txt` | — | Opcional; só compara a estrutura da MEF com a do YAML. |

Cada linha de uma suíte é interpretada como uma sequência de símbolos de entrada, **um dígito por símbolo**, aplicada a partir do estado inicial. Arquivos como `HInput.txt`, `logH.txt` e `size.txt` não são utilizados.

## 5. Como executar

Execute os comandos **a partir da raiz do projeto**, com o ambiente virtual ativado. Por padrão, o dataset é lido de `data/mefs-markov` e os resultados são gravados em `results/` (nunca dentro do dataset).

**Benchmark inteiro:**

```bash
python src/run_benchmark.py
```

**Uma instância específica (todos os modelos e métodos disponíveis):**

```bash
python src/run_benchmark.py --structure 4-4-4 --instance 1
```

**Um modelo e um método específicos:**

```bash
python src/run_benchmark.py --structure 4-4-4 --instance 1 \
  --model markov-model-1.yaml --method H
```

**Todas as instâncias de uma estrutura:**

```bash
python src/run_benchmark.py --structure 6-4-4
```

**Listar as instâncias encontradas sem processá-las:**

```bash
python src/run_benchmark.py --list
```

**Processar diretamente uma pasta de instância:**

```bash
python src/process_instance.py --instance-dir data/mefs-markov/4-4-4/1
```

### Opções

| Opção | Efeito |
|---|---|
| `--root DIR` | Raiz do benchmark (padrão: `data/mefs-markov`). Use `examples` para o exemplo mínimo. |
| `--structure`, `--instance` | Limitam o processamento a uma estrutura (ex.: `4-4-4`) e/ou instância (ex.: `1`). |
| `--model markov-model-1.yaml` | Limita o processamento a um modelo. |
| `--method H\|HSI\|P\|W\|PY\|all` | Escolhe a suíte; o padrão `all` usa todas as disponíveis. |
| `--output-root DIR` | Grava em `DIR/<estrutura>/<instância>/<modelo>/` (padrão: `results/`). |
| `--overwrite` | Recalcula CSVs já existentes. Por padrão, saídas existentes são puladas, o que permite retomar uma execução interrompida. |
| `--verbose` | Mostra uma linha por arquivo gerado (e quantos avisos de validação ele teve). |
| `--list` | Só lista as instâncias que seriam processadas. |

**Volume:** o benchmark completo tem 1.400 instâncias × 100 modelos × 5 suítes = cerca de 700 mil CSVs. As estruturas `4-4-4` a `10-4-4` (≈ 200 mil CSVs) ocupam cerca de 1,5 GB; estime **vários GB** para o benchmark inteiro. Use `--structure`, `--instance`, `--model` ou `--method` para limitar o volume, e `--output-root` para gravar em outro disco.

## 6. Saídas geradas

Os resultados são gravados **somente em CSV**, um arquivo por combinação (modelo, método), em:

```text
results/
└── 4-4-4/                              # estrutura
    └── 1/                              # instância
        └── markov-model-1/
            ├── markov-model-1_H.csv
            ├── markov-model-1_HSI.csv
            ├── markov-model-1_P.csv
            ├── markov-model-1_W.csv
            └── markov-model-1_PY.csv
```

Só são criados arquivos para as suítes existentes na instância. As gravações são atômicas: uma execução interrompida não deixa CSV truncado.

Cada CSV contém uma linha por caso de teste:

| Coluna | Descrição |
|---|---|
| `model_file` | Arquivo YAML do modelo (ex.: `markov-model-1.yaml`). |
| `suite_method`, `suite_file` | Método (`H`, `HSI`, `P`, `W`, `PY`) e arquivo de suíte usado. |
| `processing_time_s` | Tempo total do processamento do par modelo/suíte. |
| `h1_time_s` | Tempo de H1 (pontuações + ranking). |
| `h2_time_s` | Tempo de H2 (cálculo de π + pontuações + ranking). |
| `id` | Identificador do caso (`CT001`, `CT002`, …, na ordem da suíte). |
| `input_sequence` | Sequência de entrada do caso (um dígito por símbolo). |
| `transition_sequence` | Transições percorridas (`t1-t5-…`, ids na ordem de `transitions` do YAML). |
| `state_sequence` | Estados visitados, incluindo o inicial. |
| `score_h1`, `rank_h1` | Pontuação e posição do caso segundo H1. |
| `score_h2`, `rank_h2` | Pontuação e posição do caso segundo H2. |
| `same_rank` | `True` se `rank_h1 == rank_h2`. |

**Formatação:** as pontuações têm duas casas decimais; pontuações muito pequenas usam notação científica com duas casas (ex.: `4.65e-06`) para não aparecerem como `0.00`. Os tempos têm 9 casas decimais. O arredondamento é só de exibição: os cálculos e a ordenação usam precisão completa.

Erros de processamento do benchmark são registrados em `results/benchmark_errors.log`.

### Resultados não são versionados

Os CSVs são regeneráveis e muito volumosos (GBs). Para compartilhar um conjunto de resultados, publique-o fora do git (por exemplo, como anexo de uma *release* do GitHub ou no Zenodo), junto com `runtime_summary.csv` e a descrição do hardware usado.

## 7. Consolidação dos tempos

`consolidate_results.py` reúne os tempos H1/H2 de todos os CSVs em um único arquivo (`results/runtime_summary.csv`), com uma linha por (`Configuration`, `FSM ID`, `Markov ID`, `TestSuite`) e as colunas `H1 Runtime` e `H2 Runtime` (segundos):

```bash
python src/consolidate_results.py                       # só 4-4-4 (padrão)
python src/consolidate_results.py --config 4-4-4 6-4-4  # várias configurações
python src/consolidate_results.py --config all          # todas as estruturas em results/
python src/consolidate_results.py --rebuild             # relê tudo (após reprocessar)
```

Execuções seguintes só leem arquivos novos. Outras opções: `--results DIR` (pasta de resultados) e `--output FILE`. CSVs sem as colunas `h1_time_s`/`h2_time_s` são ignorados com aviso.

## 8. Como o processamento funciona

```text
run_benchmark.py
        │ descobre as instâncias selecionadas
        ▼
process_instance.py
        │ seleciona o modelo YAML e a suíte de teste
        ▼
fsm_model_io.py ────────► carrega e valida a MEF probabilística
        │
suite_io.py ────────────► lê os casos e reconstrói estados/transições
        │
plain_fsm_io.py ────────► valida opcionalmente a estrutura com fsm1.txt
        │
h1_h2_core.py ──────────► calcula H1, H2 e as posições dos casos
        │
        ▼
process_instance.py ────► grava um CSV por modelo e método
```

Para cada combinação de **modelo YAML + método da suíte**:

1. Carrega e valida o modelo probabilístico.
2. Lê as sequências de entrada da suíte.
3. Percorre a MEF a partir do estado inicial para descobrir as transições e os estados visitados por cada caso.
4. Calcula as pontuações H1 e H2 de cada caso.
5. Ordena os casos separadamente por cada pontuação e atribui as posições nos dois rankings.
6. Grava o CSV.

### As heurísticas

**H1 — produto das probabilidades das transições.** Multiplica as probabilidades de todas as transições percorridas pela sequência de entrada: a probabilidade do caminho de transições, conforme o modelo.

**H2 — produto das probabilidades estacionárias dos estados visitados.** Calcula a distribuição estacionária π da cadeia de Markov e multiplica π(s) de cada estado visitado, incluindo repetições e o estado inicial.

Os casos são classificados em ordem decrescente de pontuação, separadamente para H1 e H2. Em caso de empate, a ordenação (estável) mantém a ordem original da suíte.

**Estados sem transições de saída:** para calcular π, o código adiciona uma transição artificial de probabilidade 1 para o estado inicial, só na matriz usada nesse cálculo. Ela não altera o modelo original nem o cálculo de H1.

## 9. Reprodutibilidade

- **Determinístico:** `score_*`, `rank_*`, `transition_sequence` e `state_sequence` são idênticos entre execuções e máquinas.
- **Dependente da máquina:** os campos `*_time_s` variam com hardware, carga e versões de Python/NumPy.
- O tempo de H2 inclui o cálculo de π; o de H1 não depende dele. O tempo de leitura dos arquivos só entra em `processing_time_s`.

## 10. Testes

```bash
pytest
```

Os testes cobrem o cálculo de π, H1 e H2 em uma cadeia de 2 estados com valores conferidos à mão, o tratamento de empates e de estados sem saída, os leitores (YAML, `fsm1.txt`, suítes) e a execução ponta a ponta sobre `examples/`. Não dependem do dataset completo.

## 11. Premissas e limitações

- A seção `transitions` do YAML é a fonte das transições e probabilidades. A `transition_matrix`, quando presente, só é usada para conferência. **Nos modelos inspecionados ela diverge de `transitions` em todos os arquivos** (a matriz parece guardar uma única transição por par origem→destino, em vez de somá-las); por isso os avisos correspondentes são esperados e não afetam os resultados.
- Os avisos de validação (soma de probabilidades, `transition_matrix`, estados sem saída, divergência com `fsm1.txt`) são calculados, mas **não são impressos nem gravados no CSV**; com `--verbose`, a saída mostra apenas quantos avisos cada arquivo teve.
- Os campos de entrada e saída são usados para reconstruir os caminhos dos casos; H1 usa as probabilidades das transições e H2 as dos estados.
- `final_states` é carregado, mas os casos são percorridos até o fim da sequência de entrada, sem parar ao visitar um estado final.
- O formato das suítes (um dígito por símbolo de entrada) foi inferido dos arquivos do benchmark e não consta na documentação original. Alfabetos com 10 ou mais símbolos de entrada exigiriam outro separador.
- A distribuição estacionária pressupõe uma cadeia irredutível (ergódica). Estados sem saída recebem a transição artificial descrita acima; outros casos de cadeia não irredutível não são tratados.
- A suíte PY (`tsspy.txt`) é processada, mas não consta na documentação original do benchmark.
