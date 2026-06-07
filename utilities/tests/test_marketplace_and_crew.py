"""Sanity check tests for skill_marketplace + agents packages.

Run: python utilities/tests/test_marketplace_and_crew.py
"""
import sys
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def test_skill_marketplace():
    from backend.services.skill_marketplace import (
        SkillManifest, ManifestError, validate_manifest,
        install_skill, remove_skill, InstallError,
        list_installed, validate_for_publish,
    )
    from backend.services.skill_marketplace.manifest import ALLOWED_PERMISSIONS

    # Valid manifest
    m = validate_manifest({
        "id": "test-skill",
        "name": "Test",
        "description": "x",
        "permissions": ["web"],
    })
    assert m.id == "test-skill"
    print("OK: valid manifest accepted")

    # Bad ID
    try:
        validate_manifest({"id": "BadID", "name": "x", "description": "x"})
        raise AssertionError("Bad id was accepted")
    except ManifestError:
        print("OK: bad id rejected")

    # Unknown permission
    try:
        validate_manifest({
            "id": "test", "name": "x", "description": "x",
            "permissions": ["nuke-stuff"],
        })
        raise AssertionError("Unknown permission accepted")
    except ManifestError:
        print("OK: unknown permission rejected")

    # Bad semver
    try:
        validate_manifest({
            "id": "test", "name": "x", "description": "x",
            "version": "one",
        })
        raise AssertionError("Bad semver accepted")
    except ManifestError:
        print("OK: bad semver rejected")

    # Dangerous permissions
    m = validate_manifest({
        "id": "shell-test", "name": "x", "description": "x",
        "permissions": ["shell", "web"],
    })
    assert m.has_dangerous_permissions() == ["shell"]
    print("OK: dangerous permissions correctly identified")

    # ID validation rejects path traversal
    for bad_id in ["../etc", "foo/bar", "foo\\bar"]:
        try:
            validate_manifest({"id": bad_id, "name": "x", "description": "x"})
            raise AssertionError(f"Path-traversal id accepted: {bad_id}")
        except ManifestError:
            pass
    print("OK: path-traversal ids rejected")


def test_agents():
    from backend.services.agents import (
        AgentRole, ROLE_DEFINITIONS, Scratchpad, CrewEvent, CrewEventType,
        is_crew_request,
    )
    from backend.services.agents.crew import _parse_plan

    # Detector tests
    assert is_crew_request(
        "plan my trip and book the hotel and write the itinerary completely"
    )
    print("OK: detector fires on multi-domain requests")

    assert is_crew_request("use crew mode to handle this")
    print("OK: detector fires on explicit crew keyword")

    assert not is_crew_request("hello")
    print("OK: detector ignores trivial messages")

    assert not is_crew_request("what is 2+2")
    print("OK: detector ignores short queries")

    # Scratchpad
    sp = Scratchpad()
    sp.write("researcher", "finding", "Paris is the capital of France")
    sp.write("writer", "draft", "Final report")
    assert len(sp.entries()) == 2
    assert len(sp.by_role("researcher")) == 1
    sp.set("plan", {"steps": ["a", "b"]})
    assert sp.get("plan")["steps"] == ["a", "b"]
    print("OK: scratchpad read/write/kv working")

    rendered = sp.render(max_chars=200)
    assert "researcher" in rendered
    print("OK: scratchpad render produces readable output")

    # Plan parsing - well-formed
    plan_json = (
        '{"subtasks": ['
        '{"role": "researcher", "task": "find x", "depends_on": []},'
        '{"role": "writer", "task": "write report", "depends_on": [0]}'
        ']}'
    )
    subs = _parse_plan(plan_json)
    assert len(subs) == 2
    assert subs[0].role == AgentRole.RESEARCHER
    assert subs[1].depends_on == [0]
    print("OK: plan parsing works on well-formed JSON")

    # Plan parsing - wrapped in code fences
    fenced = "```json\n" + plan_json + "\n```"
    subs2 = _parse_plan(fenced)
    assert len(subs2) == 2
    print("OK: plan parsing extracts JSON from code fences")

    # Plan parsing - garbage
    assert _parse_plan("not json at all") == []
    assert _parse_plan("") == []
    print("OK: bad plan returns empty list")

    # Plan parsing - unknown role falls back
    odd = '{"subtasks": [{"role": "wizard", "task": "cast a spell"}]}'
    subs3 = _parse_plan(odd)
    assert len(subs3) == 1
    assert subs3[0].role == AgentRole.RESEARCHER
    print("OK: unknown role falls back to researcher")

    # Role definitions completeness
    for role in AgentRole:
        assert role in ROLE_DEFINITIONS
        d = ROLE_DEFINITIONS[role]
        assert d.system_prompt
        assert isinstance(d.allowed_tools, list)
    print("OK: every role has a complete definition")

    # CrewEvent serialization
    ev = CrewEvent(CrewEventType.AGENT_RESULT, {"role": "researcher", "result": "done"})
    d = ev.to_dict()
    assert d["type"] == "agent_result"
    assert d["role"] == "researcher"
    print("OK: CrewEvent serializes correctly")


if __name__ == "__main__":
    print("=" * 60)
    print("Skill Marketplace tests")
    print("=" * 60)
    test_skill_marketplace()
    print()
    print("=" * 60)
    print("Agents (Crew Mode) tests")
    print("=" * 60)
    test_agents()
    print()
    print("ALL SANITY CHECKS PASSED")
