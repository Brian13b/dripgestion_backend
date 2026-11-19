"""Errores de negocio compartidos por los servicios; los controllers los traducen a HTTP."""


class PermisoDenegado(ValueError):
  """El usuario no puede operar sobre ese recurso (HTTP 403)."""


class NoEncontrado(ValueError):
  """El recurso no existe en la empresa del usuario (HTTP 404)."""


class Conflicto(ValueError):
  """La operación choca con algo ya existente (HTTP 409)."""
