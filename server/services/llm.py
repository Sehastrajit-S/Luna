# Backward-compat shim — all logic lives in backend.services.llm package
from backend.services.llm import *  # noqa: F401, F403
from backend.services.llm import LLMClient, ollama
