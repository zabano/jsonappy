# Validation checklist

Run these checks before a release or after changes to package boundaries:

- Run the full test suite with the `dev` extra installed. Tests use local
  fixtures and SQLite and must not require external services or credentials.
- Build the wheel and source distribution and run `twine check` on both.
- Test wheel and source-distribution installs in clean environments for core,
  each adapter extra, and `all`. Run relevant tests outside the source tree
  and verify that unselected frameworks are absent.
- Execute the README examples with the required adapter extras installed.
- Check that the source distribution includes source modules, tests,
  documentation, and `AGENTS.md`.
- Keep examples and fixtures general-purpose, using resources such as
  articles, authors, and organizations.

See [Development](development.md) for installation, test, and build commands.
