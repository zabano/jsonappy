# Validation checklist

Run these checks before a release or after changes to package boundaries:

- Run the full test suite with the `dev` extra installed. Tests use local
  fixtures and SQLite and must not require external services or credentials.
- Build the wheel and source distribution and run `twine check` on both.
- Install the wheel in a clean environment with no optional dependencies.
  Verify resource imports and query parsing outside the source tree.
- Install each adapter extra and verify its imports outside the source tree.
- Execute the README examples with the required adapter extras installed.
- Check that the source distribution includes source modules, tests,
  documentation, and `AGENTS.md`.
- Keep examples and fixtures general-purpose, using resources such as
  articles, authors, and organizations.

See [Development](development.md) for installation, test, and build commands.
