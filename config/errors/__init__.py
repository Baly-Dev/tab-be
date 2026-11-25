"""Errori condivisi tra moduli (solo ciò che è realmente globale)."""

from config.errors.http import http_exception_from_domain

__all__ = ["http_exception_from_domain"]
