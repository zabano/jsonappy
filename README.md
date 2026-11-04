# jsonappy

Declarative JSON:API resources, query handling, and framework adapters for Python.

Requires Python 3.12 or later (below Python 4).

Define your public resources once, validate client query options, apply them
to SQLAlchemy statements, and serialize objects into JSON:API documents.
The resource and query layers have no third-party dependencies. Pydantic,
FastAPI, and SQLAlchemy are optional adapters.

## Installation

Until the first public release, install from this checkout:

```bash
python -m pip install -e '.[all]'
```

Choose extras explicitly from the checkout:

| Install command | Provides |
| --- | --- |
| `python -m pip install -e .` | Dependency-free resources and queries |
| `python -m pip install -e '.[pydantic]'` | Document serialization and mutation validation |
| `python -m pip install -e '.[fastapi]'` | FastAPI helpers and Pydantic |
| `python -m pip install -e '.[sqlalchemy]'` | SQLAlchemy query translation |
| `python -m pip install -e '.[all]'` | All adapters |

Extras can be combined, for example `'.[pydantic,sqlalchemy]'`. Adapter imports
require their corresponding extras. See [package metadata](pyproject.toml) for
exact dependency bounds. The project is alpha; public APIs may change.

## Define and serialize a resource

```python
from dataclasses import dataclass

from jsonappy.resource import Resource, String
from jsonappy.adapters.pydantic import serialize_document


@dataclass
class Article:
    id: int
    title: str


class ArticleResource(Resource):
    type = "articles"
    title = String(sortable=True, filterable=True, required=True)


document = serialize_document(Article(1, "Hello"), ArticleResource)
assert document.to_payload() == {
    "data": {
        "type": "articles",
        "id": "1",
        "attributes": {"title": "Hello"},
    },
}
```

## Add FastAPI endpoints

```python
from fastapi import FastAPI
from jsonappy.adapters.fastapi import (
    JSONAPIQuery,
    JSONAPIResponse,
    collection_response,
    install_jsonapi_exception_handlers,
)

app = FastAPI()
install_jsonapi_exception_handlers(app)


@app.get("/articles", response_class=JSONAPIResponse)
def articles(query: JSONAPIQuery):
    return collection_response(
        [Article(1, "Hello")], ArticleResource, query=query,
    )
```

Response helpers apply `include` and `fields[...]`. Apply filtering, sorting,
and pagination to your data query separately; the example above uses a fixed
in-memory list. See the [adapter guide](docs/adapters.md).

## Documentation

Start with the [documentation index](docs/README.md) for the reading order.

- [Resources, public names, and relationships](docs/resources.md)
- [Query parsing, filtering, and pagination](docs/queries.md)
- [Serialization, linkage, and includes](docs/serialization.md)
- [SQLAlchemy and FastAPI integration](docs/adapters.md)
- [Create/update validation](docs/mutations.md)
- [Architecture and current limitations](docs/architecture.md)
- [Development and PyCharm setup](docs/development.md)
- [Validation checklist](docs/validation.md) and [release preparation](docs/publishing.md)

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
python -m mypy
python -m build
python -m twine check dist/*
```

The package ships inline type annotations and a `py.typed` marker. CI checks
the library and consumer examples with mypy, runs docstring examples, and
executes the Python examples in this README and the user guides.

Licensing has not yet been selected. Add a license before public distribution.
