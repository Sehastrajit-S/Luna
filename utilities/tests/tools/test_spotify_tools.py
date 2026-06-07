from __future__ import annotations

import unittest

from tests.tools import _bootstrap  # noqa: F401


class SpotifyToolTests(unittest.TestCase):
    def test_direct_command_parser(self) -> None:
        from backend.services.command_parser import parse_user_spotify_request

        cases = {
            "play shape of you": {"action": "play", "query": "shape of you"},
            "play Shape of You on spotify": {"action": "play", "query": "shape of you"},
            "queue shape of you": {"action": "queue", "query": "shape of you"},
            "pause spotify": {"action": "pause"},
            "next song": {"action": "next"},
            "previous song": {"action": "prev"},
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(parse_user_spotify_request(message, None), expected)

    def test_service_auth_state_is_readable(self) -> None:
        from backend.services.spotify import spotify_service

        self.assertIsInstance(spotify_service._ready, bool)
        self.assertIsInstance(spotify_service.is_connected, bool)
        self.assertIsInstance(spotify_service.needs_auth, bool)
        if spotify_service.needs_auth:
            self.assertTrue(spotify_service.get_auth_url().startswith("https://"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
