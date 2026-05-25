"""Serveradmin - Query Builder Facade

Copyright (c) 2024 InnoGames GmbH

This module provides a facade for switching between SQL generator implementations.
The implementation is selected via the SQL_GENERATOR_VERSION Django setting.
"""

from django.conf import settings


def get_server_query(attribute_filters, related_vias):
    """
    Build a query for filtering servers based on attribute filters.

    This function delegates to either the v1 (raw SQL) or v2 (Django ORM)
    implementation based on the SQL_GENERATOR_VERSION setting.

    Args:
        attribute_filters: List of (Attribute, Filter) tuples to apply
        related_vias: Dict mapping attribute_id to related_via configurations

    Returns:
        str: Raw SQL query string (v1)
        QuerySet: Django QuerySet (v2)
    """
    version = getattr(settings, 'SQL_GENERATOR_VERSION', 'v1')

    if version == 'v2':
        from serveradmin.serverdb.sql_generator_v2 import (
            get_server_query as v2_query,
        )
        return v2_query(attribute_filters, related_vias)
    else:
        from serveradmin.serverdb.sql_generator import (
            get_server_query as v1_query,
        )
        return v1_query(attribute_filters, related_vias)
