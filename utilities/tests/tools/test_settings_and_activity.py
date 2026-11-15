import asyncio
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


class SettingsStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        from backend.services import settings_store as store

        self.store = store
        self.tmp = Path(tempfile.mkdtemp())
        self.env = self.tmp / ".env"
        self.personal = self.tmp / ".env.personal"
        self.env.write_text("# my comment\nUSER_NAME=friend\nollama_model=qwen2.5:7b\nweather_city=New York\n"
                            "github_token=ghp_abcdefgh12345678\n", encoding="utf-8")
        self.personal.write_text("weather_city=Tempe\n", encoding="utf-8")
        self.patches = [
            mock.patch.object(store, "_env_files", return_value=(str(self.env), str(self.personal))),
            mock.patch.object(store, "reload_settings"),
            mock.patch.object(store, "TOKEN_PATH", self.tmp / "local_api_token"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_secrets_are_masked_and_options_include_current_value(self) -> None:
        with mock.patch.object(self.store.settings, "github_token", "ghp_abcdefgh12345678"), \
             mock.patch.object(self.store, "_ollama_models", new=mock.AsyncMock(return_value=["llama3:8b"])), \
             mock.patch.object(self.store.settings, "ollama_model", "qwen2.5:7b"):
            data = asyncio.run(self.store.read_settings())
        fields = {f["key"]: f for f in data["fields"]}
        self.assertEqual(fields["github_token"]["value"], "")
        self.assertEqual(fields["github_token"]["masked"], "••••5678")
        self.assertNotIn("ghp_", str(data))
        self.assertEqual(fields["ollama_model"]["options"], ["qwen2.5:7b", "llama3:8b"])

    def test_writes_merge_into_existing_lines_and_the_defining_file(self) -> None:
        result = self.store.update_settings({"user_name": "Sehas", "weather_city": "Phoenix",
                                             "github_token": "", "llm_context_window": "32768"})
        env = self.env.read_text(encoding="utf-8")
        self.assertIn("# my comment", env)                               # untouched
        self.assertIn("USER_NAME=Sehas", env)                            # file's own key casing kept
        self.assertIn("github_token=ghp_abcdefgh12345678", env)          # blank secret = keep
        self.assertIn("llm_context_window=32768", env)                   # new key appended
        self.assertIn("weather_city=New York", env)                      # not edited here…
        self.assertEqual(self.personal.read_text(encoding="utf-8"), "weather_city=Phoenix\n")   # …but where it's defined
        self.assertEqual(result["updated"], ["llm_context_window", "user_name", "weather_city"])

    def test_invalid_values_write_nothing(self) -> None:
        before = self.env.read_text(encoding="utf-8")
        for bad in ({"llm_context_window": "10"}, {"llm_provider": "skynet"}, {"ollama_base_url": "ftp://x"},
                    {"github_default_repo": "not a repo"}, {"user_name": "a\nOPENAI_API_KEY=evil"},
                    {"db_url": "sqlite:///x"}, {"user_name": "ok", "llm_context_window": "abc"}):
            with self.subTest(bad=bad), self.assertRaises(self.store.SettingsError):
                self.store.update_settings(bad)
        self.assertEqual(self.env.read_text(encoding="utf-8"), before)

    def test_values_with_spaces_are_quoted(self) -> None:
        self.store.update_settings({"user_name": "Sehas Selva"})
        self.assertIn('USER_NAME="Sehas Selva"', self.env.read_text(encoding="utf-8"))

    def test_token_is_created_once_and_checked(self) -> None:
        token = self.store.local_api_token()
        self.assertEqual(token, self.store.local_api_token())
        self.assertTrue(self.store.token_ok(token))
        self.assertFalse(self.store.token_ok("nope"))
        self.assertFalse(self.store.token_ok(None))

    def test_put_without_token_is_forbidden(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.routers.settings import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        self.assertEqual(client.put("/api/settings", json={"user_name": "x"}).status_code, 403)
        ok = client.put("/api/settings", json={"user_name": "Luna Fan"},
                        headers={"X-Luna-Token": self.store.local_api_token()})
        self.assertEqual(ok.status_code, 200)
        bad = client.put("/api/settings", json={"llm_context_window": "5"},
                         headers={"X-Luna-Token": self.store.local_api_token()})
        self.assertEqual(bad.status_code, 422)


class ActivityCalendarTests(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from backend.models.database import Base, Conversation, Message

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.Conversation, self.Message = Conversation, Message

    def _msg(self, local_dt: datetime, conv, role="user", text="hi"):
        utc = local_dt.astimezone().astimezone(timezone.utc).replace(tzinfo=None)
        self.db.add(self.Message(conversation_id=conv.id, role=role, content=text, created_at=utc))

    def test_days_levels_topics_and_most_active(self) -> None:
        from backend.services.activity_calendar import month_activity

        conv = self.Conversation(title="SatPV outline"); self.db.add(conv); self.db.commit()
        for h in range(9):
            self._msg(datetime(2026, 9, 10, 21, 0) + timedelta(minutes=h), conv)   # 9 evening messages
        self._msg(datetime(2026, 9, 10, 21, 30), conv, role="assistant")           # assistant not counted
        self._msg(datetime(2026, 9, 11, 23, 50), conv)                             # late night stays on the 11th
        self.db.commit()
        data = month_activity(self.db, 2026, 9)
        day10, day11 = data["days"][9], data["days"][10]
        self.assertEqual((day10["messages"], day10["level"], day10["topics"]), (9, 3, ["SatPV outline"]))
        self.assertEqual((day11["messages"], day11["level"]), (1, 1))
        self.assertEqual(data["total_messages"], 10)
        self.assertEqual(data["active_days"], 2)
        self.assertEqual(data["most_active"], "Evenings")
        self.assertEqual(len(data["days"]), 30)

    def test_streak_counts_back_from_today_or_yesterday(self) -> None:
        from backend.services.activity_calendar import current_streak

        conv = self.Conversation(); self.db.add(conv); self.db.commit()
        today = date(2026, 9, 23)
        for offset in (1, 2, 3, 5):                                               # gap on day -4
            self._msg(datetime.combine(today - timedelta(days=offset), datetime.min.time()) + timedelta(hours=12), conv)
        self.db.commit()
        self.assertEqual(current_streak(self.db, today=today), 3)                 # today not over yet
        self._msg(datetime.combine(today, datetime.min.time()) + timedelta(hours=9), conv); self.db.commit()
        self.assertEqual(current_streak(self.db, today=today), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
