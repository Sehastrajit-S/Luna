"""Generic skill runtime. Use cases live in server/skills/<id>/ as data + instructions."""
from server.services.skill_runtime.registry import (
    SearchSkill,
    all_ask_replies,
    choose_skill_with_model,
    get_search_skill,
    load_search_skills,
    pick_search_skill,
)
from server.services.skill_runtime.runner import SkillRun, run_search_skill, run_web_search

__all__ = [
    "SearchSkill",
    "SkillRun",
    "all_ask_replies",
    "choose_skill_with_model",
    "get_search_skill",
    "load_search_skills",
    "pick_search_skill",
    "run_search_skill",
    "run_web_search",
]
