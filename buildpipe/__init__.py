"""Portable Silent Ridge build pipeline (H01).

Independent of event infrastructure. Each child module performs one stage and is
safe to import on Windows: stages that require a Linux build host raise
`BuildEnvironmentError` instead of guessing.
"""

__version__ = "h01.1"


class BuildEnvironmentError(RuntimeError):
    """A stage needs a capability this host does not have (Linux, qemu/nbd, guest)."""
