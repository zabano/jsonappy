# Preparing a public release

[Documentation index](README.md) · [Validation checklist](validation.md)

This checkout is alpha (`0.1.0` in package metadata) and is being prepared for
its first public release. The owner has selected the [MIT License](../LICENSE),
which is declared in package metadata. Actual project URLs still need to be
supplied before release; contributors must not invent them.

## Owner decisions

Before the first release, the owner must:

1. Confirm availability of the `jsonappy` distribution and repository names.
2. Confirm that the selected MIT license text and copyright notice are included
   in release artifacts and match package metadata. License changes require
   the owner's direction.
3. Supply actual repository, issue tracker, and documentation URLs for
   `[project.urls]`; do not guess URLs.
4. Approve the release version, author metadata, supported Python versions,
   dependency bounds, and public API scope.
5. Explicitly authorize publication. Building or reviewing the package does
   not authorize a public release.

## Verify release artifacts

Follow [Development](development.md) and complete the [validation checklist](validation.md).
Build a wheel and source distribution with no stale versions in the output
directory, run `twine check`, and test both artifacts outside the checkout with
all five installation profiles. Inspect packaged documentation and verify that
installation commands, API names, and dependency bounds match the artifacts.

The current CI workflow tests and builds packages; it does not publish them.
After the owner's decisions and artifact verification, configure an approved
release workflow or upload to TestPyPI with the owner's account. Verify the
TestPyPI installation and metadata before the owner-authorized PyPI release.
Keep credentials and deployment configuration out of this library.

After publication, update checkout-only installation guidance and status claims
in the README and documentation index to reflect the actual available release.

## Conformance claims

The FastAPI header checks provide basic media-type handling. They do not
implement complete Accept quality negotiation or JSON:API extension/profile
negotiation. Do not advertise full JSON:API conformance without a separate
specification audit. See [Architecture](architecture.md#scope-and-current-limitations)
for the current integration scope.
