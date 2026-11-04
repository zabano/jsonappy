"""Optional integrations translating resources and queries into frameworks.

Import pydantic for document models and serialization, fastapi for HTTP
helpers, or sqlalchemy for ORM query construction. Install the corresponding
package extra before importing an integration. This namespace imports no
integrations eagerly, preserving dependency-free core imports.
"""
