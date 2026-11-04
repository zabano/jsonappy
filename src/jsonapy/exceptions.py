"""Exception namespace reserved for package-wide errors.

Concrete errors currently live beside their implementations, such as
jsonapy.query.filtering.FilterResolutionError and
jsonapy.adapters.pydantic.SerializationError. Import those errors from their
owning modules; no common exception base is defined here.
"""
