"""Google Workspace and Microsoft 365 integration helpers."""
from backend.services.workspace_integrations.base import (
    WorkspaceIntegrationError,
    WorkspaceResponse,
    integration_status,
)
from backend.services.workspace_integrations.google import google_workspace
from backend.services.workspace_integrations.microsoft import microsoft_workspace

__all__ = [
    "WorkspaceIntegrationError",
    "WorkspaceResponse",
    "google_workspace",
    "microsoft_workspace",
    "integration_status",
]
