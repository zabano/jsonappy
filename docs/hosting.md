# Documentation site

[Documentation index](README.md) · Related: [Development](development.md)

The site uses [MkDocs](https://www.mkdocs.org/) with its bundled Read the Docs
theme, search, and explicit navigation. Read the Docs builds the site using
`.readthedocs.yaml`. The separate GitHub Actions Documentation workflow checks
builds on every push and pull request, including Markdown-only changes, and
uploads the HTML as the `documentation-site` artifact.

## Build and preview locally

From the repository root, create a separate documentation environment:

```bash
python -m venv .venv-docs
source .venv-docs/bin/activate
python -m pip install -r docs/site/requirements.txt
python -m mkdocs serve --config-file docs/site/mkdocs.yml
```

Open the local address printed by MkDocs, normally `http://127.0.0.1:8000`.
To produce the same strict build used by CI and Read the Docs:

```bash
python -m mkdocs build --strict --config-file docs/site/mkdocs.yml
```

The output is written to `site/`, which is ignored by Git. Missing navigation
pages, broken local links, and invalid anchors fail the build. External links
are not fetched or checked. Documentation tooling is not a library runtime
dependency and does not require installing jsonappy or its optional adapters.

## Sources and links

Markdown pages stay directly in `docs/`. All MkDocs tooling lives in
`docs/site/`: `mkdocs.yml`, `requirements.txt`, and `hooks.py`. The root
`.readthedocs.yaml` and `.github/workflows/docs.yml` point to this configuration.
The tooling directory is excluded from the published site.

Edit the existing Markdown sources. `docs/README.md` is the site overview;
the root README becomes the Quickstart page. The changelog and license also
become pages. `docs/site/hooks.py` adds these pages in memory and rewrites
repository-relative links during builds, so no generated Markdown needs to be
committed. Links to repository configuration and contributor instructions point
to the actual GitHub repository instead of nonexistent site pages.

Keep pages in `docs/site/mkdocs.yml` navigation and run the strict build above
when changing documentation or the build hook. The existing executable example tests
remain separate from rendering; run them using the development environment as
described in [Development](development.md#documentation-examples-and-typing).

## Connect Read the Docs

The repository configuration is ready for hosting. An owner must complete the
account connection on Read the Docs; this does not happen from local builds:

1. Commit and push the configuration to GitHub.
2. Sign in to [Read the Docs](https://app.readthedocs.org/) with GitHub and grant
   its GitHub App access to `zabano/jsonappy`.
3. Choose **Add project**, select the repository, and use `main` as its default
   branch. Keep the configuration path `.readthedocs.yaml`.
4. Trigger a build and inspect its logs. The project's actual hostname is
   assigned there; do not assume a particular Read the Docs slug is available.
5. Under **Settings → Pull request builds**, confirm preview builds are enabled.
6. Keep `latest` for development. After the first release tag exists, activate
   that version and configure `stable`/the default version as appropriate.
7. Add the assigned documentation URL to the README and `[project.urls]` after
   verifying the hosted site.

Read the Docs supplies `READTHEDOCS_CANONICAL_URL`; `docs/site/mkdocs.yml` uses it for the
canonical URL of the version being built. Local and GitHub Actions builds work
without that variable. No hosting credentials belong in the repository.

See the official guides for [adding a project](https://docs.readthedocs.com/platform/stable/intro/add-project.html),
[pull request previews](https://docs.readthedocs.com/platform/stable/pull-requests.html),
and [versions](https://docs.readthedocs.com/platform/stable/versions.html).
