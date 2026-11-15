# Backward-compat shim — all logic lives in backend.services.workspace_integrations package
from backend.services.workspace_integrations import *  # noqa: F401, F403
from backend.services.workspace_integrations import (
    WorkspaceIntegrationError,
    WorkspaceResponse,
    google_workspace,
    microsoft_workspace,
    integration_status,
)
