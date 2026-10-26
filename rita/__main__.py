"""Permite `python -m rita` (y `uv run -m rita`), que no depende de la instalación del paquete."""

import sys

from .main import main

sys.exit(main())
