"""Run migrations with ``python3 -m apps.backend.migrations``."""

from .runner import main


if __name__ == "__main__":
    raise SystemExit(main())
