"""Exception namespace reserved for package-wide errors.

Concrete errors currently live beside their implementations, such as
jsonappy.query.filtering.FilterResolutionError and
jsonappy.adapters.pydantic.SerializationError. Import those errors from their
owning modules; no common exception base is defined here.
"""
