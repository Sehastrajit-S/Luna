# Luna Skills

Skills teach Luna how to handle specific types of requests. They are plain text files — no code required. Anyone can write one.

---

## How it works

When a user sends a message, Luna checks all installed skills and follows the matching skill's instructions. A skill is just a folder with a few files that tell Luna:

- **what kind of request it handles** (`SKILL.md`)
- **what tools it can use** (`skill.json`)
- **how to format output** for the desktop app (`electron.md`) and terminal (`cli.md`)

Luna loads skills from two places:
- `skills/` — built-in skills (this folder)
- `data/workspace/skills/` — user-installed skills (created at runtime)

---

## Folder structure

```
skills/
└── your-skill-name/
    ├── skill.json     ← required: metadata, permissions, tools
    ├── SKILL.md       ← required: instructions Luna follows
    ├── electron.md    ← optional: extra rules for the desktop UI
    └── cli.md         ← optional: extra rules for the terminal / CLI
```

Only `skill.json` and `SKILL.md` are required. Luna works fine without the UI-specific files.

---

## Step-by-step: create your first skill

### 1. Create the folder

Name it after what the skill does, lowercase with hyphens:

```
skills/recipe-finder/
```

### 2. Write `skill.json`

This tells Luna when to activate the skill and what it is allowed to do.

```json
{
  "id": "recipe-finder",
  "name": "Recipe Finder",
  "description": "Find, adapt, and suggest recipes based on ingredients or dietary needs.",
  "permissions": ["web"],
  "tools": ["web_search", "web_fetch"]
}
```

**Fields:**

| Field | Required | What it does |
|---|---|---|
| `id` | yes | Unique identifier. Match the folder name. |
| `name` | yes | Human-readable name shown in the UI. |
| `description` | yes | One sentence. Luna uses this to decide if your skill matches a request. Make it specific. |
| `permissions` | yes | What system areas the skill can access. See table below. |
| `tools` | yes | Which tools Luna can call. See table below. |

**Available permissions:**

| Permission | Grants access to |
|---|---|
| `web` | Internet search and page fetching |
| `workspace` | Reading and writing files in `data/workspace/` |
| `shell` | Running shell commands (use with caution) |
| `confirm-shell-commands` | Requires user approval before each shell command |

**Available tools:**

| Tool | What it does |
|---|---|
| `web_search` | Quick web search, returns snippets |
| `web_research` | Deep web research with source comparison |
| `web_fetch` | Fetch the full content of a URL |
| `browser_read` | Read the current browser page |
| `browser_open` | Open a URL in the browser |
| `workspace_read` | Read a file from the workspace |
| `workspace_write` | Write a file to the workspace |
| `code_read_file` | Read a code file (max 100 KB) |
| `code_write_file` | Write or overwrite a code file |
| `code_edit_file` | Replace exact text in a code file |
| `code_list_files` | List files in a workspace directory |
| `code_search` | Regex/text search across workspace files |
| `code_run_shell` | Run a shell command in the workspace |

Only list the tools your skill actually needs. Fewer is better.

---

### 3. Write `SKILL.md`

This is the main instruction file. Luna reads it before responding to any request that matches your skill. Write it like you are briefing a very capable assistant.

```markdown
# Recipe Finder

Use this skill when the user asks for recipes, meal ideas, ingredient substitutions, or dietary adaptations.

## Workflow

1. Ask clarifying questions if ingredients or dietary needs are unclear.
2. Search the web for recipes matching the request.
3. Fetch the top 1–2 results to get the actual recipe content.
4. Present the recipe in a clean, readable format: ingredients list, then steps.
5. Suggest one substitution or variation at the end.
6. If no matching recipe is found, suggest the closest alternative and explain why.

## Output format

- Use a numbered list for steps.
- Use a bullet list for ingredients.
- Keep instructions concise — one action per step.
- Do not include ads, author bios, or filler text from fetched pages.
```

**Tips for a good `SKILL.md`:**

- Start with "Use this skill when…" — this helps Luna decide when to activate it.
- Write a numbered **Workflow** so Luna follows a consistent process.
- Be specific about what to include and what to leave out in the output.
- Keep it under ~150 lines. Luna only reads the first ~4000 characters.

---

### 4. Write `electron.md` (optional)

Extra rules for when Luna is running as the desktop app. Append these on top of `SKILL.md` — you do not need to repeat the base instructions.

```markdown
# Recipe Finder — Desktop UI rules

- After presenting the recipe, add a [WIDGET:steps|Step 1: ...|Step 2: ...|Step 3: ...] widget.
- Use [WIDGET:summary|Prep time: ...|Cook time: ...|Serves: ...] for the at-a-glance card.
- Do not use widgets for simple one-line answers.
```

The desktop app can render structured widgets. Use them when the content has a natural visual structure (steps, comparisons, tables, timelines).

---

### 5. Write `cli.md` (optional)

Extra rules for when Luna is running in the terminal. Keep output plain and compact.

```markdown
# Recipe Finder — CLI rules

- No widgets or special commands — the terminal cannot render them.
- Keep the full recipe under 40 lines. Offer to show more if needed.
- Use plain dashes for ingredient bullets, plain numbers for steps.
```

---

### 6. Test it

Restart Luna (or reload the backend) and ask something your skill is designed for. Luna will log which skill is active in the terminal.

You can also check via the CLI:

```bash
npm run luna -- skills
```

---

## Real examples

Browse the existing skills for reference:

| Skill | Good example of |
|---|---|
| [`research/`](research/) | Web search + source comparison + widgets |
| [`coding-agent/`](coding-agent/) | Tool-heavy workflow, workspace + shell access |
| [`resume-checker/`](resume-checker/) | File reading + web lookup + structured output |
| [`document-drafter/`](document-drafter/) | Pure writing skill, no tools needed |
| [`job-application-assistant/`](job-application-assistant/) | Multi-step interactive workflow |

---

## Common mistakes

**Skill never activates** — the `description` in `skill.json` is too vague. Make it describe the exact type of request, not the skill's internal behaviour.

**Luna ignores the workflow** — `SKILL.md` is too long or too abstract. Break it into a short numbered list. Luna follows lists more reliably than paragraphs.

**Output looks wrong in the app** — you have formatting rules in `SKILL.md` that conflict with `electron.md`. Put UI-specific rules only in `electron.md`.

**Shell commands run without asking** — add `"confirm-shell-commands"` to `permissions` in `skill.json`. Luna will ask the user before each command.

---

## Starter template

A ready-to-copy template lives in [`_template/`](_template/). It contains all four files pre-filled with comments explaining every field. Copy the folder, rename it, fill in the blanks, and delete the comment blocks.

```bash
# from the repo root
cp -r skills/_template skills/my-new-skill
```

---

## Contributing

1. Copy `skills/_template/` into a new folder under `skills/`.
2. Fill in the four files — rename `_template` references to your skill name.
3. Test locally against a few real prompts.
4. Open a pull request with a short description of what the skill does and two or three example prompts that trigger it.

Skills do not require any Python or JavaScript knowledge — if you can write clear instructions, you can write a skill.
