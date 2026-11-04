"""Keep README and user-guide examples aligned with the installed API."""

from pathlib import Path
import re
import sys
from types import ModuleType

import pytest
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


@pytest.mark.parametrize("guide", [
    "resources", "queries", "serialization", "adapters", "mutations",
])
def test_guide_python_examples(guide, monkeypatch):
    if guide == "adapters":
        pytest.importorskip("sqlalchemy")
    path = Path(__file__).resolve().parents[1] / "docs" / f"{guide}.md"
    examples = re.findall(r"^```python\n(.*?)^```", path.read_text(), re.M | re.S)
    assert examples, f"{guide} must contain executable Python examples"

    module = ModuleType(f"guide_{guide}")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    for index, example in enumerate(examples, start=1):
        exec(compile(example, f"{path}:example-{index}", "exec"), module.__dict__)

    if guide == "mutations":
        with TestClient(module.app) as client:
            response = client.patch(
                "/articles/1", headers={"Content-Type": "application/vnd.api+json"},
                json={"data": {"type": "articles", "id": "1",
                               "attributes": {"headline": "Updated"}}},
            )
            assert response.status_code == 200
            assert response.json() == {
                "meta": {"id": "1", "attributes": {"title": "Updated"}},
            }
            invalid = client.patch(
                "/articles/1", headers={"Content-Type": "application/vnd.api+json"},
                json={"data": {"type": "articles", "id": "2"}},
            )
            assert invalid.status_code == 409
            assert invalid.json()["errors"][0]["source"]["pointer"] == "/data/id"
