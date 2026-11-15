# Backward-compat shim — all logic lives in backend.services.command_parser package
from backend.services.command_parser import *  # noqa: F401, F403
from backend.services.command_parser import (
    is_coding_request,
    parse_user_launch_request,
    parse_user_map_request,
    parse_user_spotify_request,
    extract_direct_research_query,
    extract_direct_dataset_query,
    user_is_leaving,
    response_is_farewell,
    parse_commands,
    execute_commands,
)
