"""Reuse root Markdown files and adapt repository links for the docs site.

Only MkDocs loads this hook. It changes in-memory build content, preserving
Markdown links that readers use directly on GitHub.
"""

from pathlib import Path

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import File, Files


def on_files(files: Files, config: MkDocsConfig) -> Files:
    """Add quickstart, changelog, and license pages without duplicating sources."""
    root = Path(config.config_file_path).resolve().parents[2]
    repository = config.repo_url.rstrip("/")
    root_pages = {
        "quickstart.md": "README.md",
        "changelog.md": "CHANGELOG.md",
        "license.md": "LICENSE",
    }
    for destination, source in root_pages.items():
        content = (root / source).read_text(encoding="utf-8")
        if source == "LICENSE":
            content = "# License\n\n```text\n" + content + "```\n"
        if source == "README.md":
            content = content.replace("](docs/", "](")
            content = content.replace("](CHANGELOG.md", "](changelog.md")
            content = content.replace("](LICENSE)", "](license.md)")
            content = content.replace("](pyproject.toml)", f"]({repository}/blob/main/pyproject.toml)")
        files.append(File.generated(config, destination, content=content))

    for file in files.documentation_pages():
        content = file.content_string
        for source, destination in {
            "../README.md": "quickstart.md",
            "../CHANGELOG.md": "changelog.md",
            "../LICENSE": "license.md",
            "../pyproject.toml": f"{repository}/blob/main/pyproject.toml",
            "../AGENTS.md": f"{repository}/blob/main/AGENTS.md",
            "../.github/workflows/tests.yml": f"{repository}/blob/main/.github/workflows/tests.yml",
        }.items():
            content = content.replace(f"]({source}", f"]({destination}")
        file.content_string = content
    return files
