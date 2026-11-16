# Job Application Assistant

Tailor resumes, draft cover letters, write recruiter messages, and prep for interviews — all grounded in the actual job post.

## What it does

Reads the job post (or fetches it from a URL), extracts requirements, responsibilities, seniority signals, keywords, and compensation. Compares the post against your resume or profile when available. Drafts application materials specific to the role. All claims are grounded in your actual background — missing facts are asked for, never invented.

## When it activates

When you ask for help applying to jobs, tailoring materials, comparing roles, drafting cover letters, writing recruiter outreach, or prepping for interviews.

## Example prompts

- "Help me apply to this job posting: [URL]"
- "Tailor my resume for a senior backend engineer role at a fintech company"
- "Write a cover letter for a product manager role focused on AI tools"
- "Draft a cold message to a hiring manager at Anthropic"
- "What interview questions should I expect for this role?"

## Tools used

| Tool | Purpose |
|---|---|
| `web_fetch` | Fetch job post content from a URL |
| `web_research` | Research the company, role, and industry context |
| `workspace_read` | Read your resume from the workspace |
| `workspace_write` | Save drafted materials to the workspace |

## Output

- Role summary (responsibilities, requirements, seniority, comp)
- Fit and gaps (where you match, where you don't)
- Tailoring plan (what to emphasize, what to add)
- Draft material or saved workspace path
- References for job-post claims and company facts

## Files

| File | Purpose |
|---|---|
| `skill.json` | Metadata, permissions, tools |
| `SKILL.md` | Workflow instructions |
| `electron.md` | Desktop widget rules |
| `cli.md` | Terminal formatting rules |
