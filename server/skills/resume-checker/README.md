# Resume Checker

Review, score, rewrite, and tailor resumes against a specific job post.

## What it does

Reads your resume from the workspace or accepts pasted text. Optionally fetches the target job post for comparison. Evaluates role fit, missing keywords, impact and specificity of bullets, ATS readability, and formatting risks. Gives direct findings first — no flattery. Rewrites weak bullets when there's enough context, and suggests metric placeholders rather than inventing numbers.

## When it activates

When you ask to review, improve, tailor, score, or rewrite a resume, CV, LinkedIn profile, or job application material.

## Example prompts

- "Review my resume and tell me what to fix"
- "Tailor my resume for this job posting: [URL]"
- "Rewrite the weak bullet points in my resume"
- "How ATS-friendly is my resume?"
- "Score my resume for a senior data scientist role"

## Tools used

| Tool | Purpose |
|---|---|
| `workspace_read` | Read your resume from the workspace |
| `web_research` | Research the target role and company requirements |
| `web_fetch` | Fetch job post content from a URL |
| `workspace_write` | Save the revised resume to the workspace |

## Output

- Overall fit (for the target role if provided)
- Critical fixes (ordered by impact)
- Bullet rewrites (action, scope, result, evidence)
- ATS and keyword notes
- Saved workspace path if a revised resume was created

## What it won't do

Invent jobs, degrees, dates, certifications, companies, or metrics. If a number doesn't exist in your background, it asks rather than fabricates.

## Files

| File | Purpose |
|---|---|
| `skill.json` | Metadata, permissions, tools |
| `SKILL.md` | Workflow instructions |
| `electron.md` | Desktop widget rules |
| `cli.md` | Terminal formatting rules |
