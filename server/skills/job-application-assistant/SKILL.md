# Job Application Assistant

Use this skill when the user asks for help applying to jobs, tailoring materials, comparing roles, or drafting cover letters and recruiter messages.

Workflow:

1. Read the job post or fetch it with `web_fetch` when a URL is provided.
2. Extract requirements, responsibilities, seniority signals, location, compensation if visible, and keywords.
3. Compare the job post against the user's resume or profile when available.
4. Draft application materials that are specific to the role:
   - Resume targeting notes.
   - Cover letter.
   - Recruiter message.
   - Interview prep bullets.
5. Keep claims grounded in the user's actual background. Ask for missing facts instead of inventing.
6. Save requested drafts with `workspace_write`.
7. Include source references for job-post claims and company facts.

Output format:

- Role summary.
- Fit and gaps.
- Tailoring plan.
- Draft material or saved file path.
- References.
