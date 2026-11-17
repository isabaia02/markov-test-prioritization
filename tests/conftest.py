import os
import textwrap

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES_ROOT = os.path.join(PROJECT_ROOT, "examples")
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

# Cadeia de 2 estados cujos valores de pi, H1 e H2 são calculáveis à mão:
#   pi_A = 0.4, pi_B = 0.6  (equilíbrio: 0.75*pi_A = 0.5*pi_B)
TOY_YAML = textwrap.dedent("""\
    states:
      - A
      - B
    initial_state: A
    final_states:
      - B
    transitions:
      - A,0,0,A,0.25
      - A,1,1,B,0.75
      - B,0,0,A,0.5
      - B,1,1,B,0.5
""")


@pytest.fixture
def toy_model_path(tmp_path):
    path = tmp_path / "toy.yaml"
    path.write_text(TOY_YAML, encoding="utf-8")
    return str(path)


@pytest.fixture
def write_yaml(tmp_path):
    def _write(text, name="model.yaml"):
        path = tmp_path / name
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        return str(path)
    return _write
