"""Scheduled job functions — events, tasks, memory, personality, patterns."""
import re
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from server.models.database import SessionLocal, CalendarEvent, Task, ProactiveLog, Message
from server.services.scheduler.notifications import send_windows_notification, proactive_queue

_VISION_CHECKIN_SYSTEM = (
    "You are Luna, a quiet and attentive AI companion. "
    "You have a live picture of what this person is working on and what is happening in their world. "
    "You initiate conversation naturally — brief, warm, grounded in what you actually know. "
    "You are not a data dashboard. You speak like a present, perceptive person would — "
    "when there's something genuinely worth saying. One clear observation is enough."
)

_VISION_CHECKIN_PROMPT = """\
━━ CONTEXT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Time: {time_str}, {day_name} — quiet {quiet_min}

RECENT CONVERSATION (what they've been working on / thinking about)
{convo}

OPEN TASKS
{tasks}

TODAY'S SCHEDULE
{events}

LIVE DATA (use ONLY if it relates to what they're doing or discussed)
Weather: {weather}
Market:
{market}
Top headlines:
{news}

━━ DECIDE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are a quiet, attentive presence — speak when you have something real to say.

ONE clear reason is enough to speak. You do not need multiple signals.

SPEAK when any of these are true:
  → They've been at it for a while — acknowledge what they're working on naturally
  → There's recent conversation you can follow up on or continue
  → A market move, headline, or event touches something they care about or mentioned
  → It's been a long quiet stretch and a light check-in fits

DO NOT report raw data unprompted. Lead with them, not the data.
If you use live data, make it specific to their situation — not a broadcast.

Default toward speaking if you have a reasonable observation. SILENT is for when you genuinely have nothing.

Reply with SILENT or 1 message (≤ 18 words, conversational, no prefix, no quotes)."""


def vision_aware_checkin():
    """
    Every few minutes, pull full live context (weather, market, news,
    calendar, conversation) and let the LLM decide whether the specific moment
    warrants Luna initiating. Pushes immediately to the SSE bus.
    """
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        local_now = datetime.now()

        # Silence window: 1 am – 7 am LOCAL time
        if 1 <= local_now.hour < 7:
            return

        # Don't interrupt active conversation (user spoke in last 5 min)
        last_user = (
            db.query(Message)
            .filter(Message.role == "user")
            .order_by(Message.created_at.desc())
            .first()
        )
        if last_user:
            quiet_min = (now - last_user.created_at.replace(tzinfo=None)).total_seconds() / 60
            if quiet_min < 5:
                return
        else:
            quiet_min = 9999

        # Throttle: at most once every 15 minutes
        last_proactive = (
            db.query(ProactiveLog)
            .filter(ProactiveLog.reason == "vision_aware_checkin")
            .order_by(ProactiveLog.sent_at.desc())
            .first()
        )
        if last_proactive:
            since_min = (now - last_proactive.sent_at.replace(tzinfo=None)).total_seconds() / 60
            if since_min < 15:
                return

        # ── Weather ───────────────────────────────────────────────────────────
        from server.services.dashboard import weather as _weather, markets as _markets
        from server.services.dashboard import news as _news_mod
        wx = _weather.get_cached_weather()
        if wx:
            weather_str = (
                f"{wx.get('temp_f', '?')}°F, {wx.get('condition', '?')}, "
                f"humidity {wx.get('humidity', '?')}%, wind {wx.get('wind_mph', '?')} mph "
                f"({wx.get('city', 'local')})"
            )
        else:
            weather_str = "Not available."

        # ── Market ────────────────────────────────────────────────────────────
        stocks = _markets.get_cached_stocks()
        if stocks:
            market_lines = []
            for s in stocks:
                stale = " (prev close)" if s.get("stale") else ""
                market_lines.append(f"  {s['symbol']} ${s['price']:,.2f} {s['pct']:+.2f}%{stale}")
            market_str = "\n".join(market_lines)
        else:
            market_str = "Not available."

        # ── News (top 5 headlines) ────────────────────────────────────────────
        news_cache = getattr(_news_mod, "_news_cache", [])
        if news_cache:
            news_str = "\n".join(
                f"  • {item.get('title', '')}"
                for item in news_cache[:5]
                if item.get("title")
            )
        else:
            news_str = "Not available."

        # ── Conversation ──────────────────────────────────────────────────────
        recent_msgs = (
            db.query(Message)
            .order_by(Message.created_at.desc())
            .limit(6)
            .all()
        )
        convo_snippet = "\n".join(
            f"  {'User' if m.role == 'user' else 'Luna'}: {m.content[:120]}"
            for m in reversed(recent_msgs)
        ) or "  None."

        # ── Calendar + Tasks ──────────────────────────────────────────────────
        today_end = now.replace(hour=23, minute=59)
        events = db.query(CalendarEvent).filter(
            CalendarEvent.start_datetime >= now,
            CalendarEvent.start_datetime <= today_end,
        ).limit(3).all()
        events_str = ", ".join(e.title for e in events) or "None"

        open_tasks = db.query(Task).filter(Task.completed == False).limit(4).all()
        tasks_str = ", ".join(t.title for t in open_tasks) or "None"

        quiet_label = f"{int(quiet_min)} min" if quiet_min < 9999 else "a long time"

        prompt = _VISION_CHECKIN_PROMPT.format(
            time_str=local_now.strftime("%I:%M %p"),
            day_name=local_now.strftime("%A"),
            weather=weather_str,
            market=market_str,
            news=news_str,
            quiet_min=quiet_label,
            convo=convo_snippet,
            events=events_str,
            tasks=tasks_str,
        )

        try:
            loop = asyncio.new_event_loop()
            from server.services.llm import ollama as _ollama
            reply = loop.run_until_complete(
                _ollama.complete(prompt, system=_VISION_CHECKIN_SYSTEM, temperature=0.72)
            )
            loop.close()
            reply = reply.strip().strip('"').strip("'")
        except Exception as e:
            print(f"[vision_checkin] LLM call failed: {e}")
            return

        if not reply or reply.upper() == "SILENT" or len(reply) < 4:
            print("[vision_checkin] SILENT — nothing worth saying right now.")
            return

        # Push to real-time SSE bus (appears immediately on dashboard)
        from server.services.proactive_bus import push as _bus_push
        _bus_push(reply)

        # Also enqueue for next chat pickup
        proactive_queue.append(reply)

        db.add(ProactiveLog(message=reply, reason="vision_aware_checkin"))
        db.commit()
        print(f"[vision_checkin] -> {reply}", flush=True)

    except Exception as e:
        print(f"[vision_checkin] failed: {e}")
    finally:
        db.close()


# (kind, id, stage, scheduled time) already announced — each reminder fires once.
_announced: set[tuple] = set()
REMIND_BEFORE_MIN = 15


def _announce(db: Session, key: tuple, message: str, reason: str) -> None:
    if key in _announced:
        return
    _announced.add(key)
    send_windows_notification("Luna", message)
    proactive_queue.append(message)
    db.add(ProactiveLog(message=message, reason=reason))


def check_upcoming_events():
    """Runs every minute: events get a heads-up 15 minutes before and a nudge
    at start time; tasks get a nudge when they fall due. Each fires once.
    Stored times are UTC."""
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        events = (
            db.query(CalendarEvent)
            .filter(CalendarEvent.start_datetime >= now - timedelta(minutes=2),
                    CalendarEvent.start_datetime <= now + timedelta(minutes=REMIND_BEFORE_MIN))
            .all()
        )
        for event in events:
            minutes = round((event.start_datetime - now).total_seconds() / 60)
            if minutes <= 1:
                _announce(db, ("event", event.id, "start", event.start_datetime),
                          f"'{event.title}' is starting now.", "event_start")
            else:
                _announce(db, ("event", event.id, "before", event.start_datetime),
                          f"Heads up — '{event.title}' starts in {minutes} minutes.", "upcoming_event")

        due = (
            db.query(Task)
            .filter(Task.completed == False,  # noqa: E712
                    Task.due_date >= now - timedelta(minutes=2), Task.due_date <= now + timedelta(minutes=1))
            .all()
        )
        for task in due:
            _announce(db, ("task", task.id, "due", task.due_date), f"Reminder: '{task.title}' is due now.", "task_due")
        db.commit()
    finally:
        db.close()


def check_overdue_tasks():
    """Notify about overdue tasks once per day."""
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        overdue = (
            db.query(Task)
            .filter(Task.completed == False, Task.due_date < now)
            .all()
        )
        if overdue:
            names = ", ".join(t.title for t in overdue[:3])
            extra = f" (+{len(overdue) - 3} more)" if len(overdue) > 3 else ""
            msg = f"You have overdue tasks: {names}{extra}"
            send_windows_notification("Luna", msg)
            proactive_queue.append(msg)
            db.add(ProactiveLog(message=msg, reason="overdue_tasks"))
            db.commit()
    finally:
        db.close()


def sync_spotify_activity():
    """Reconcile the tracked 'listening' activity with real Spotify playback state."""
    db: Session = SessionLocal()
    try:
        from server.services.activity_tracker import ActivityTracker
        ActivityTracker(db).sync_spotify_activity()
    except Exception as e:
        print(f"[activity] Spotify sync failed: {e}")
    finally:
        db.close()


def daily_memory_compaction():
    """Merge redundant/duplicate facts once a day at 3am."""
    db: Session = SessionLocal()
    try:
        from server.services.memory_manager import MemoryManager
        manager = MemoryManager(db)
        loop = asyncio.new_event_loop()
        removed = loop.run_until_complete(manager.compact_facts())
        loop.close()
        if removed > 0:
            print(f"[memory] Compaction complete — removed {removed} redundant facts.")
    except Exception as e:
        print(f"[memory] Compaction failed: {e}")
    finally:
        db.close()


def daily_personality_decay():
    """Decay personality preferences slightly toward neutral each day."""
    db: Session = SessionLocal()
    try:
        from server.services.personality import PersonalityEngine
        engine = PersonalityEngine(db)
        engine.daily_decay()
    finally:
        db.close()


def morning_greeting():
    """Send a morning greeting notification."""
    msg = "Morning. Ready when you are."
    send_windows_notification("Luna", msg)
    proactive_queue.append(msg)
    db: Session = SessionLocal()
    try:
        db.add(ProactiveLog(message=msg, reason="morning_greeting"))
        db.commit()
    finally:
        db.close()


def confidence_decay():
    """
    Decay confidence of stale preference and goal facts slightly each week.
    Prevents outdated beliefs from competing equally with fresh information.
    Min confidence floor is 0.3 — facts are never deleted, just de-prioritised.
    """
    db: Session = SessionLocal()
    try:
        from server.models.database import Fact
        cutoff = datetime.utcnow() - timedelta(days=30)
        stale = (
            db.query(Fact)
            .filter(
                Fact.is_active == True,
                Fact.category.in_(["preference", "goal"]),
                Fact.updated_at <= cutoff,
            )
            .all()
        )
        for f in stale:
            f.confidence = max(0.3, round(f.confidence - 0.04, 4))
        if stale:
            db.commit()
            print(f"[memory] Decayed confidence for {len(stale)} stale preference/goal facts.")
    except Exception as e:
        print(f"[memory] Confidence decay failed: {e}")
    finally:
        db.close()


def state_aware_proactive():
    """
    Check the current user state and send a contextual proactive message
    when the state warrants it. Runs every 10 minutes alongside the existing
    companion_check_in, but state-specific messaging takes priority.
    """
    db: Session = SessionLocal()
    try:
        from server.services.state_engine import state_engine
        state = state_engine.infer_passive(db)
        now = datetime.utcnow()

        # Throttle: don't repeat state messages within 60 minutes
        recent = (
            db.query(ProactiveLog)
            .filter(ProactiveLog.reason.in_(["state_staying_up", "state_just_woke_up", "state_back_from_work"]))
            .order_by(ProactiveLog.sent_at.desc())
            .first()
        )
        if recent:
            since_min = (now - recent.sent_at.replace(tzinfo=None)).total_seconds() / 60
            if since_min < 60:
                return

        msg = None
        reason = None

        if state.value == "STAYING_UP":
            msg = "It's late and you've been active for a while.\n\nShould I switch to focus mode or set a sleep reminder?"
            reason = "state_staying_up"

        elif state.value == "JUST_WOKE_UP":
            today_end = now.replace(hour=23, minute=59)
            tasks = (
                db.query(Task)
                .filter(Task.completed == False, Task.due_date <= today_end)
                .limit(3).all()
            )
            events = (
                db.query(CalendarEvent)
                .filter(CalendarEvent.start_datetime >= now, CalendarEvent.start_datetime <= today_end)
                .limit(3).all()
            )
            parts = ["Morning. I'll keep it brief."]
            if events:
                ev_str = ", ".join(e.title for e in events)
                parts.append(f"You have: {ev_str} today.")
            if tasks:
                t_str = ", ".join(t.title for t in tasks)
                parts.append(f"Open tasks: {t_str}.")
            if not events and not tasks:
                parts.append("Nothing urgent on the schedule.")
            msg = "\n\n".join(parts)
            reason = "state_just_woke_up"

        elif state.value == "BACK_FROM_WORK":
            msg = "Welcome back. You sound like you might be tired.\n\nWant a quick summary or should I stay quiet?"
            reason = "state_back_from_work"

        if msg:
            proactive_queue.append(msg)
            send_windows_notification("Luna", msg.split("\n\n")[0])
            db.add(ProactiveLog(message=msg, reason=reason))
            db.commit()
    except Exception:
        pass
    finally:
        db.close()


def companion_check_in():
    """
    Let Luna initiate after a quiet stretch — message is LLM-generated from
    recent conversation context so it never repeats the same static line.
    """
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()

        last_user_msg = (
            db.query(Message)
            .filter(Message.role == "user")
            .order_by(Message.created_at.desc())
            .first()
        )
        if not last_user_msg:
            return

        last_ts = last_user_msg.created_at.replace(tzinfo=None)

        # Only check in during today's conversation window
        if last_ts.date() < now.date():
            return

        quiet_minutes = (now - last_ts).total_seconds() / 60
        if quiet_minutes < 25 or quiet_minutes > 180:
            return

        recent_proactive = (
            db.query(ProactiveLog)
            .filter(ProactiveLog.reason == "companion_check_in")
            .order_by(ProactiveLog.sent_at.desc())
            .first()
        )
        if recent_proactive:
            since_last = (now - recent_proactive.sent_at.replace(tzinfo=None)).total_seconds() / 60
            if since_last < 90:
                return

        recent_msgs = (
            db.query(Message)
            .order_by(Message.created_at.desc())
            .limit(6)
            .all()
        )
        context = "\n".join(
            f"{'User' if m.role == 'user' else 'Luna'}: {m.content[:120]}"
            for m in reversed(recent_msgs)
        )

        prompt = (
            f"The conversation ended {int(quiet_minutes)} minutes ago.\n\n"
            f"Recent exchange:\n{context}\n\n"
            "Generate a single short unprompted message from Luna to check in naturally. "
            "Rules: max 2 sentences, no questions asking how they are, not clingy, "
            "could be a random thought or gentle observation rooted in what was discussed. "
            "Match Luna's terse, warm-but-not-gushing style."
        )

        try:
            loop = asyncio.new_event_loop()
            from server.services.llm import ollama as _ollama
            msg = loop.run_until_complete(
                _ollama.complete(
                    prompt,
                    system="You are Luna. Be brief. No emojis. No terms of endearment.",
                    temperature=0.85,
                )
            )
            loop.close()
            msg = msg.strip().strip('"')[:240]
        except Exception:
            return

        if not msg or len(msg) < 5:
            return

        proactive_queue.append(msg)
        db.add(ProactiveLog(message=msg, reason="companion_check_in"))
        db.commit()
    except Exception:
        pass
    finally:
        db.close()


_COMMITMENT_RE = re.compile(
    r'\b('
    r'tomorrow|next week|'
    r'next (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|'
    r'this (?:friday|thursday|wednesday|tuesday|monday|weekend)|'
    r'tonight|later today|in a few days|'
    r'(?:interview|presentation|exam|test|deadline|surgery|appointment|flight)'
    r')\b',
    re.IGNORECASE,
)


def mine_behavioral_patterns():
    """
    Mine StateEvent table to detect recurring patterns (peak hours, stress days,
    late-night tendency) and store them as long-term behavioral facts.
    Runs daily at 4 am — enough data accumulates within a week.
    """
    db: Session = SessionLocal()
    try:
        from server.models.database import StateEvent, Fact
        from collections import Counter

        cutoff = datetime.utcnow() - timedelta(days=30)
        events = db.query(StateEvent).filter(StateEvent.timestamp >= cutoff).all()
        if len(events) < 20:
            return  # not enough data yet

        patterns: list[str] = []
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                     "Friday", "Saturday", "Sunday"]

        hour_counts = Counter(e.hour for e in events)
        if hour_counts:
            peak_hour = hour_counts.most_common(1)[0][0]
            ampm = "am" if peak_hour < 12 else "pm"
            h12 = peak_hour % 12 or 12
            patterns.append(f"User is most active around {h12}{ampm}")

        day_emotions: dict[int, list[str]] = {}
        for e in events:
            if e.emotion and e.emotion not in ("neutral", "calm"):
                day_emotions.setdefault(e.day_of_week, []).append(e.emotion)
        for dow, emotions in day_emotions.items():
            if len(emotions) < 5:
                continue
            dominant, count = Counter(emotions).most_common(1)[0]
            if dominant in ("sad", "angry", "stressed") and count / len(emotions) > 0.5:
                patterns.append(f"User often feels {dominant} on {day_names[dow]}s")

        late = sum(1 for e in events if e.hour >= 23 or e.hour < 4)
        if late / len(events) > 0.3:
            patterns.append("User is frequently active late at night")

        if not patterns:
            return

        mem_db: Session = SessionLocal()
        try:
            from server.models.database import Fact
            from server.services.memory_manager import MemoryManager
            manager = MemoryManager(mem_db)
            loop = asyncio.new_event_loop()
            saved = 0
            for pattern in patterns:
                already = mem_db.query(Fact).filter(
                    Fact.content.ilike(f"%{pattern[:35]}%"),
                    Fact.is_active == True,
                    Fact.category == "behavior",
                ).first()
                if not already:
                    loop.run_until_complete(
                        manager.store_fact(
                            pattern, "behavior",
                            memory_type="long",
                            importance=0.7,
                            source="pattern_mining",
                        )
                    )
                    saved += 1
            loop.close()
            if saved:
                print(f"[patterns] Stored {saved} new behavioral pattern(s).")
        finally:
            mem_db.close()
    except Exception as e:
        print(f"[patterns] Mining failed: {e}")
    finally:
        db.close()


def proactive_commitment_followup():
    """
    Scan user messages from 1–6 days ago for future-tense commitments (interviews,
    exams, appointments, etc.). If the event has likely passed, generate a follow-up.
    Throttled to one follow-up per 24 hours.
    """
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()

        recent = (
            db.query(ProactiveLog)
            .filter(ProactiveLog.reason == "commitment_followup")
            .order_by(ProactiveLog.sent_at.desc())
            .first()
        )
        if recent:
            hours_since = (now - recent.sent_at.replace(tzinfo=None)).total_seconds() / 3600
            if hours_since < 24:
                return

        start = now - timedelta(days=6)
        end   = now - timedelta(hours=20)

        messages = (
            db.query(Message)
            .filter(Message.role == "user", Message.created_at.between(start, end))
            .order_by(Message.created_at.desc())
            .limit(40)
            .all()
        )

        for msg in messages:
            if not _COMMITMENT_RE.search(msg.content):
                continue

            hours_ago = (now - msg.created_at.replace(tzinfo=None)).total_seconds() / 3600
            prompt = (
                f"The user said this {int(hours_ago)} hours ago:\n\"{msg.content[:200]}\"\n\n"
                "If the event or commitment mentioned has LIKELY ALREADY HAPPENED based on the "
                "time elapsed, write one short natural follow-up from Luna "
                "(e.g. 'How'd the interview go?' / 'Did the exam happen?'). "
                "If it hasn't passed yet or is unclear, reply with empty string exactly: \"\""
            )

            try:
                loop = asyncio.new_event_loop()
                from server.services.llm import ollama as _ollama
                followup = loop.run_until_complete(
                    _ollama.complete(
                        prompt,
                        system="You are Luna. One sentence. No emojis. No terms of endearment.",
                        temperature=0.6,
                    )
                )
                loop.close()
                followup = followup.strip().strip('"')
            except Exception:
                continue

            if not followup or len(followup) < 5:
                continue

            proactive_queue.append(followup)
            db.add(ProactiveLog(message=followup, reason="commitment_followup"))
            db.commit()
            break  # one follow-up per run
    except Exception as e:
        print(f"[scheduler] Commitment followup failed: {e}")
    finally:
        db.close()
