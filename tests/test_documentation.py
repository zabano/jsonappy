"""Keep the README's resource and endpoint examples executable."""

from pathlib import Path
import re
import sys
from types import ModuleType

from fastapi.testclient import TestClient


def test_readme_python_examples(monkeypatch):
    readme = Path(__file__).resolve().parents[1] / "README.md"
    examples = re.findall(r"^```python\n(.*?)^```", readme.read_text(), re.M | re.S)
    assert examples, "README must contain executable Python examples"

    module = ModuleType("readme_examples")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    for index, example in enumerate(examples, start=1):
        exec(compile(example, f"{readme}:example-{index}", "exec"), module.__dict__)

    # Exercise the documented endpoint in addition to constructing its app.
    with TestClient(module.app) as client:
        response = client.get("/articles?fields[articles]=title")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.api+json"
    assert response.json() == {"data": [module.document.to_payload()["data"]]}
