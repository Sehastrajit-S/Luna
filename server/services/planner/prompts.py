"""LLM prompt templates for planner and critic."""

_PLAN_SCHEMA = """{
  "goal": "<restate goal>",
  "steps": [
    {
      "id": "s1",
      "action": "tool",
      "description": "what this step does",
      "tool_name": "tool_from_registry",
      "tool_args": {},
      "depends_on": []
    },
    {
      "id": "s2",
      "action": "llm",
      "description": "synthesise result",
      "llm_prompt": "Given this data: {s1.result} — summarise ...",
      "depends_on": ["s1"]
    }
  ]
}"""

_CRITIC_SCHEMA = """{
  "verdict": "success" | "partial" | "failure",
  "score": 0.0-1.0,
  "reasoning": "<paragraph>",
  "retry_step_ids": ["s2"]
}"""
