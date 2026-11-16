"""Seed an isolated Luna data dir with fictional demo content for README screenshots.

Usage: LUNA_DATA_DIR=<demo dir> python seed_demo.py <repo root>
Prints the id of the hero conversation.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
assert os.environ.get("LUNA_DATA_DIR"), "set LUNA_DATA_DIR to the demo folder"

from server.models.database import Attachment, Base, Conversation, Message, SessionLocal, engine, init_db  # noqa: E402

Base.metadata.create_all(bind=engine)
init_db()
db = SessionLocal()
for model in (Attachment, Message, Conversation):
    db.query(model).delete()
db.commit()

now = datetime.now(timezone.utc).replace(second=0, microsecond=0)


def convo(title, turns, hours_ago, attach=None):
    c = Conversation(title=title, started_at=now - timedelta(hours=hours_ago), message_count=len(turns))
    db.add(c)
    db.flush()
    for i, (role, text) in enumerate(turns):
        m = Message(conversation_id=c.id, role=role, content=text, created_at=now - timedelta(hours=hours_ago) + timedelta(minutes=i))
        db.add(m)
        db.flush()
        if attach and i == 0:
            for j, (name, mime, kind, size, summary) in enumerate(attach):
                db.add(Attachment(
                    id=f"demo{c.id}x{j}", conversation_id=c.id, message_id=m.id, filename=name, mime_type=mime,
                    kind=kind, size_bytes=size, summary_line=summary, created_at=m.created_at,
                ))
    return c


convo("Compare Postgres vs SQLite for a side project", [
    ("user", "Postgres or SQLite for a small side project with maybe 50 users?"),
    ("assistant", "For 50 users, **SQLite** is the simpler choice: one file, no server, and plenty fast for that load. "
                  "Move to **Postgres** when you need many concurrent writers, row-level security, or managed backups."),
], 70)
convo("Draft a polite follow-up email", [
    ("user", "Draft a short, polite follow-up to a recruiter I haven't heard back from in a week."),
    ("assistant", "**Subject:** Following up on the Product Designer role\n\nHi Priya,\n\nI hope your week is going well. "
                  "I wanted to follow up on my application and say again how excited I am about the role. "
                  "Happy to share anything else that would help.\n\nThanks for your time,\nAlex"),
], 52)
convo("Weekly grocery list under $80", [
    ("user", "Make a vegetarian grocery list for one week, under $80."),
    ("assistant", "- Oats, bananas, frozen berries\n- Lentils, chickpeas, brown rice\n- Tofu, eggs, Greek yogurt\n- Spinach, peppers, onions, tomatoes\n\nEstimated total: **$68**"),
], 30)
convo("Fix the flaky retry test", [
    ("user", "My retry test fails randomly in CI. Can you make the backoff deterministic?"),
    ("assistant", "Inject the clock and jitter so the test controls them:\n\n```python\ndef backoff(attempt, base=0.5, jitter=random.random):\n"
                  "    return base * 2 ** attempt + jitter() * 0.1\n```\n\nIn the test, pass `jitter=lambda: 0` and assert exact delays. "
                  "I saved the full version to `code/retry_backoff.py`."),
], 20)
convo("Summarize the Q3 roadmap", [
    ("user", "Summarize this roadmap in five bullets and flag anything risky."),
    ("assistant", "- **Mobile app GA** in August, after two beta rounds\n- **Offline sync** moves to Q4\n- **Pricing change** for teams over 25 seats\n"
                  "- **SOC 2** audit starts in September\n- **Hiring:** two backend engineers\n\n**Risk:** GA depends on offline sync, which just slipped a quarter."),
], 6, attach=[("q3-roadmap.pdf", "application/pdf", "pdf", 1_840_000, "PDF · 12 pages"),
              ("budget-2026.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "spreadsheet", 96_000, "Spreadsheet · 3 sheets")])
convo("Meeting notes from Monday", [
    ("user", "Turn these notes into action items with owners."),
    ("assistant", "1. **Sam:** send the vendor shortlist by Wednesday\n2. **Priya:** book the design review\n3. **Alex:** update the launch checklist"),
], 3, attach=[("standup-notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx", 24_000, "Word · 2 pages")])
hero = convo("Plan a 3-day trip to Kyoto", [
    ("user", "Plan a relaxed 3-day trip to Kyoto in April. I like gardens, food markets and quiet temples."),
    ("assistant", "Here's a slow-paced plan built around cherry-blossom season. 🌸\n\n"
                  "### Day 1 · Higashiyama\n"
                  "- Morning walk along the **Philosopher's Path** before the crowds\n"
                  "- Lunch at **Nishiki Market**: try tamagoyaki and yuba\n"
                  "- Sunset at **Kiyomizu-dera**\n\n"
                  "### Day 2 · Arashiyama\n"
                  "- **Bamboo grove** at 8 am, then the moss garden at **Gio-ji**\n"
                  "- Boat ride on the Hozu River\n\n"
                  "### Day 3 · Quiet temples\n"
                  "- **Daitoku-ji** sub-temples and their rock gardens\n"
                  "- Matcha at a tea house in Uji\n\n"
                  "**Tip:** book Saiho-ji (moss temple) two months ahead. It only takes reservations by mail or online.\n\n"
                  "References:\n"
                  "[1] Philosopher's Path - https://www.japan-guide.com/e/e3906.html\n"
                  "[2] Nishiki Market - https://kyoto.travel/en/shrine_temple/nishiki.html\n"
                  "[3] Arashiyama bamboo grove - https://www.insidekyoto.com/arashiyama-bamboo-grove\n"
                  "[4] Saiho-ji reservations - https://saihoji-kokedera.com/en/\n"
                  "[5] Kyoto cherry blossom forecast - https://www.jnto.go.jp/sakura/eng/"),
], 1)
db.commit()
print(hero.id)

workspace = Path(os.environ["LUNA_DATA_DIR"]) / "workspace"
files = {
    "reports/kyoto-itinerary.md": "# Kyoto in 3 days\n\nDay 1: Higashiyama\nDay 2: Arashiyama\nDay 3: Daitoku-ji\n",
    "datasets/austin-coffee-shops.csv": "name,neighborhood,rating\nMerit Coffee,South Congress,4.6\nCuvee,East Austin,4.5\n",
    "code/retry_backoff.py": "import random\n\n\ndef backoff(attempt, base=0.5, jitter=random.random):\n    return base * 2 ** attempt + jitter() * 0.1\n",
    "drafts/follow-up-email.md": "Subject: Following up on the Product Designer role\n",
    "reports/q3-roadmap-summary.md": "# Q3 roadmap summary\n",
}
for rel, text in files.items():
    path = workspace / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
