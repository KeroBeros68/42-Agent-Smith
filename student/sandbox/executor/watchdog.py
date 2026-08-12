"""Per-snippet execution timeout (§V.2.3).

Docker's own limits apply to the whole long-lived container, not to a single
exec call, so an individual snippet exceeding max_execution_time_seconds
must be cut here without killing the container or losing the namespace.
"""
