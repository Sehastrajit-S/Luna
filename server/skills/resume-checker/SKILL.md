# Resume Checker

Use this skill when the user asks to review, improve, tailor, score, or rewrite a resume, CV, LinkedIn profile, or job application material.

Workflow:

1. If the resume is attached to the chat, its text is already in the `<documents>` block — review it directly, without announcing that you'll read it. If it's in Luna's workspace, read it with `workspace_read`. If the user pasted text, work from that text.
2. If a target job or company is provided, use `web_research` or `web_fetch` to inspect the role, company, and key requirements.
3. Evaluate the resume on:
   - Role fit and missing keywords.
   - Impact, metrics, and specificity.
   - ATS readability.
   - Bullet strength using action, scope, result, and evidence.
   - Formatting risks such as dense blocks, unexplained acronyms, or unclear dates.
4. Give direct findings first. Do not flatter. Prioritize the highest-impact fixes.
5. Rewrite weak bullets in a stronger form when enough context exists. If metrics are missing, suggest metric placeholders rather than inventing numbers.
6. If asked to produce a revised resume, save it with `workspace_write` as Markdown, plain text, or another requested format.
7. If tailoring to a job post, include a short keyword map:
   - Requirement.
   - Evidence in resume.
   - Gap or rewrite.
8. Do not invent jobs, degrees, dates, certifications, companies, or metrics.

Output format:

- Overall fit.
- Critical fixes.
- Bullet rewrites.
- ATS/keyword notes.
- Saved file path if a revised file was created.
