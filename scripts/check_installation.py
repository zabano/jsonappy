"""Test one built distribution and optional extra in a fresh environment.

Copy relevant tests outside the checkout and check imports before running them.
Only pytest and, for HTTP tests, httpx are added as test dependencies. Package
runtime dependencies must come from the artifact's declared requirements.
"""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv


CORE_TESTS = ("query", "test_resource.py", "test_registry.py")
PYDANTIC_TESTS = ("adapters/test_pydantic.py", "adapters/test_decimal.py")
HTTP_TESTS = ("adapters/test_fastapi.py", "test_documentation.py")
PROFILES = {
    "core": (),
    "pydantic": ("pydantic",),
    "fastapi": ("pydantic", "fastapi"),
    "sqlalchemy": ("sqlalchemy",),
    "all": ("pydantic", "fastapi", "sqlalchemy"),
}

IMPORT_CHECK = """
import importlib
import importlib.util
from importlib.resources import files
import json
from pathlib import Path
import sys

import jsonapy
import jsonapy.adapters
from jsonapy import Resource, ResourceRegistry
from jsonapy.query import QuerySpec

expected = set(json.loads(sys.argv[1]))
for module in ('pydantic', 'fastapi', 'sqlalchemy'):
    present = importlib.util.find_spec(module) is not None
    assert present == (module in expected), (module, present, expected)
    if present:
        importlib.import_module('jsonapy.adapters.' + module)

package = Path(jsonapy.__file__).resolve().parent
assert package.is_relative_to(Path(sys.prefix).resolve()), package
assert files('jsonapy').joinpath('py.typed').is_file()
assert isinstance(Resource.registry, ResourceRegistry)
assert QuerySpec.parse(sort='title').sort
print(package)
"""


def run(python: Path, *arguments: str, cwd: Path) -> None:
    """Run a command with Python path isolation and propagate failures."""
    subprocess.run([str(python), "-I", *arguments], cwd=cwd, check=True)


def check_installation(artifacts: Path, distribution: str, extra: str) -> None:
    """Install an artifact and run only tests supported by its selected extra."""
    pattern = "*.whl" if distribution == "wheel" else "*.tar.gz"
    matches = sorted(artifacts.resolve().glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"Expected one {distribution} in {artifacts}, found {len(matches)}.")
    artifact = matches[0]
    checkout = Path(__file__).resolve().parents[1]
    print(f"Checking {artifact.name}, profile={extra}, Python={sys.version.split()[0]}", flush=True)

    with tempfile.TemporaryDirectory(prefix="jsonapy-install-") as temporary:
        work = Path(temporary)
        environment = work / "venv"
        venv.create(environment, with_pip=True)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        requirement = str(artifact) if extra == "core" else f"{artifact}[{extra}]"
        run(python, "-m", "pip", "install", requirement, cwd=work)

        dependencies = ["pytest>=9.1.1,<10"]
        if "fastapi" in PROFILES[extra]:
            dependencies.append("httpx>=0.27,<1")
        run(python, "-m", "pip", "install", *dependencies, cwd=work)
        run(python, "-m", "pip", "check", cwd=work)

        # Inspect the environment used for tests, including test dependencies.
        package = Path(subprocess.check_output(
            [str(python), "-I", "-c", IMPORT_CHECK, json.dumps(PROFILES[extra])],
            cwd=work, text=True,
        ).strip())

        selected = list(CORE_TESTS)
        if "pydantic" in PROFILES[extra]:
            selected.extend(PYDANTIC_TESTS)
        if "fastapi" in PROFILES[extra]:
            selected.extend(HTTP_TESTS)
        if "sqlalchemy" in PROFILES[extra]:
            selected.append("adapters/sqlalchemy")
        if extra == "all":
            selected = ["."]
        for relative in selected:
            source = checkout / "tests" / relative
            destination = work / "tests" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(source, destination)
        if "fastapi" in PROFILES[extra]:
            shutil.copy2(checkout / "README.md", work / "README.md")

        # Do not copy the checkout's pytest.ini: its pythonpath points at src.
        config = work / "pytest.ini"
        config.write_text("[pytest]\naddopts = --import-mode=importlib --doctest-modules\n")
        doctests = [package / "__init__.py", package / "resource", package / "query"]
        if extra == "all":
            doctests.append(package / "adapters")
        elif extra != "core":
            adapter = package / "adapters" / extra
            doctests.append(adapter if adapter.is_dir() else adapter.with_suffix(".py"))
        run(
            python, "-m", "pytest", "-q", "-c", str(config),
            "tests", *(str(path) for path in doctests), cwd=work,
        )


def main() -> None:
    """Select one profile and distribution for local or CI verification."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=Path("dist"))
    parser.add_argument("--distribution", choices=("wheel", "sdist"), default="wheel")
    parser.add_argument("--extra", choices=tuple(PROFILES), default="core")
    arguments = parser.parse_args()
    check_installation(arguments.artifacts, arguments.distribution, arguments.extra)


if __name__ == "__main__":
    main()
