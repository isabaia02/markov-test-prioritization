# Dados de entrada (dataset `mefs-markov`)

O dataset completo **não está versionado neste repositório** (cerca de 640 MB de entradas, ~150 mil arquivos). Ele deve ser colocado manualmente em `data/mefs-markov/`, pasta ignorada pelo git (ver `.gitignore`).

## Como obter

- **Origem / download:** FSMs geradas pelo Prof. Dr. André Takeshi Endo
- **Autoria / como citar:** 

Depois de baixar e extrair, a estrutura deve ficar assim:

```text
data/
└── mefs-markov/
    ├── 4-4-4/                  # estrutura: estados-entradas-saídas
    │   ├── 1/                  # instância (uma MEF)
    │   │   ├── fsm1.txt        # MEF no formato kiss (sem probabilidades)
    │   │   ├── tshnina.txt     # suíte de teste do método H
    │   │   ├── tshsi.txt       # suíte do método HSI
    │   │   ├── tsp3.txt        # suíte do método P
    │   │   ├── tsw.txt         # suíte do método W
    │   │   ├── tsspy.txt       # suíte do método PY (extra; fora da documentação original)
    │   │   └── markovmodels/
    │   │       ├── markov-model-1.yaml
    │   │       └── ... (100 modelos)
    │   └── 2/ ... 100/
    ├── 6-4-4/ ... 30-4-4/
```

Para testar sem o dataset, use o exemplo mínimo em [`../examples/`](../examples/), que tem exatamente o mesmo formato (`--root examples`).

## Descrição do benchmark

- Cada pasta de primeiro nível representa uma estrutura de MEFs com *X* estados, *Y* entradas e *Z* saídas. Por exemplo, `4-4-4` possui 100 MEFs com 4 estados, 4 entradas e 4 saídas.
- As estruturas disponíveis são `4-4-4`, `6-4-4`, …, `30-4-4` (14 estruturas, 100 MEFs cada: 1.400 instâncias).
- Cada instância tem `markovmodels/` com 100 modelos de Markov gerados a partir da estrutura da MEF original em `fsm1.txt`: a estrutura (estados, entradas, saídas, próximo estado) é a mesma; só as probabilidades mudam.
- Uma instância é qualquer pasta que contenha `markovmodels/`.

## Arquivos que o código não utiliza

`HInput.txt`, `logH.txt` e `size.txt`, presentes em cada instância, são ignorados.

## Avisos sobre os modelos

Nos modelos inspecionados, a seção opcional `transition_matrix` dos YAMLs diverge da lista `transitions` (a matriz parece guardar apenas uma das transições quando há várias entre o mesmo par de estados, em vez de somá-las). O código usa sempre `transitions` como fonte e só usa a matriz para conferência; ver a seção "Premissas e limitações" do [README principal](../README.md).
