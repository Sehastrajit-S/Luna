from __future__ import annotations

import unittest

from tests.tools import _bootstrap  # noqa: F401


class SystemToolTests(unittest.TestCase):
    def test_read_only_system_controls_are_callable(self) -> None:
        from backend.services import system_controls

        for fn_name in ("get_volume", "get_brightness", "get_clipboard"):
            with self.subTest(fn_name=fn_name):
                result = getattr(system_controls, fn_name)()
                self.assertIsInstance(result, tuple)
                self.assertEqual(len(result), 2)
                self.assertIsInstance(result[0], bool)

    def test_system_info_shape(self) -> None:
        from backend.services.system_controls import get_system_info

        info = get_system_info()
        self.assertIsInstance(info, dict)
        self.assertIn("os", info)
        self.assertIn("machine", info)


if __name__ == "__main__":
    unittest.main(verbosity=2)
