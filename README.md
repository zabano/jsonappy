# jsonapy

Declarative JSON:API resources, query handling, and framework adapters for Python.

Requires Python 3.14 or later (below Python 4).

Define your public resources once, validate client query options, apply them
to SQLAlchemy statements, and serialize objects into JSON:API documents.
The resource and query layers have no third-party dependencies. Pydantic,
FastAPI, and SQLAlchemy are optional adapters.

## Installation

Until the first public release, install from this checkout:

```bash
python -m pip install -e '.[all]'
```

Install only what your application uses with the `pydantic`, `fastapi`, or
`sqlalchemy` extra. A plain installation provides the core resource and query
layers. Adapter imports require their corresponding extras.

## Define and serialize a resource

```python
from dataclasses import dataclass

from jsonapy.resource import Resource, String
from jsonapy.adapters.pydantic import serialize_document


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
from jsonapy.adapters.fastapi import (
    JSONAPIQuery,
    collection_response,
    install_jsonapi_exception_handlers,
)

app = FastAPI()
install_jsonapi_exception_handlers(app)


@app.get("/articles")
def articles(query: JSONAPIQuery):
    return collection_response(
        [Article(1, "Hello")], ArticleResource, query=query,
    )
```

Response helpers apply `include` and `fields[...]`. Apply filtering, sorting,
and pagination to your data query separately; the example above uses a fixed
in-memory list. See the [adapter guide](docs/adapters.md).

## Documentation

- [Resources and field options](docs/resources.md)
- [Query parameters and filtering](docs/queries.md)
- [Framework adapters and mutation validation](docs/adapters.md)
- [Architecture and application responsibilities](docs/architecture.md)
- [Development and PyCharm setup](docs/development.md)
- [Public release preparation](docs/publishing.md)
- [Validation checklist](docs/validation.md)

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
python -m build
python -m twine check dist/*
```

Licensing has not yet been selected. Add a license before public distribution.
