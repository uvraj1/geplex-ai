"""GepLex Main Source Code Architecture Hub.

This package provides convenient high-level access to the core components of GepLex:
- app: The main FastAPI ASGI application
- core: System constants, database models, authentication, and middleware
- src: AI agent loop, LLM multi-provider core, memory, tools, and background tasks
- routes: API endpoint handlers
- services: Specialized auxiliary services
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

__version__ = "1.0.3"
__all__ = ["__version__"]
