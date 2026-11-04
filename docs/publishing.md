# Preparing a public release

This project is being prepared for its first public release.

Before the first release:

1. Confirm a unique PyPI distribution name and GitHub repository name. The
   name `jsonapy` is already used by another JSON:API project on PyPI.
2. Choose a license, add its text as `LICENSE`, and declare it in package
   metadata.
3. Add the actual repository, issue tracker, and documentation URLs to
   `[project.urls]`; do not use guessed URLs.
4. Review version, author metadata, README, supported Python versions, and
   dependency bounds. Run the full test suite and package checks.
5. Build wheel and source distribution and test installation in a clean
   environment. Check both core-only and adapter installations.
6. Configure a release workflow or upload to TestPyPI using your account,
   verify the release, then publish to PyPI when ready.

The FastAPI header checks provide basic media-type handling. They do not
implement complete Accept quality negotiation or JSON:API extension/profile
negotiation. Do not advertise full JSON:API conformance without a separate
specification audit.
