"""Test bootstrap helpers."""
from __future__ import annotations

import sys
import logging
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
warnings.simplefilter("ignore")
warnings.filterwarnings("ignore", message=r".*Pydantic V2.*")
warnings.filterwarnings("ignore", message=r".*Support for class-based `config` is deprecated.*")
warnings.filterwarnings("ignore", message=r".*`json_encoders` is deprecated.*")
warnings.filterwarnings("ignore", category=ResourceWarning)
