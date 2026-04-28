"""Runtime environment helpers for packaged vs source execution."""

from __future__ import annotations

import sys


def is_compiled_runtime() -> bool:
    """Return ``True`` when running from a packaged/compiled executable."""
    if bool(getattr(sys, "frozen", False)):
        return True

    main_module = sys.modules.get("__main__")
    # Nuitka marks compiled entrypoint modules with ``__compiled__``.
    return main_module is not None and bool(getattr(main_module, "__compiled__", False))
