from __future__ import annotations

import unittest

from tests.tools import _bootstrap  # noqa: F401


class WorkspaceToolTests(unittest.TestCase):
    def test_workspace_read_write_round_trip(self) -> None:
        from backend.services.workspace import WORKSPACE_DIR, read_workspace_file, write_workspace_file

        path = "_tests/tool_smoke.txt"
        result = write_workspace_file(path, "luna tool smoke")
        self.assertEqual(result["path"], path)
        self.assertEqual(read_workspace_file(path), "luna tool smoke")

        target = WORKSPACE_DIR / path
        if target.exists():
            target.unlink()

    def test_workspace_path_escape_is_blocked(self) -> None:
        from backend.services.workspace import read_workspace_file

        with self.assertRaises(ValueError):
            read_workspace_file("../../.env")

    def test_workspace_base64_round_trip_for_binary_files(self) -> None:
        from backend.services.workspace import WORKSPACE_DIR, read_workspace_file_base64, write_workspace_file_base64

        path = "_tests/binary.bin"
        result = write_workspace_file_base64(path, "AAECAwQ=")
        self.assertEqual(result["path"], path)
        read = read_workspace_file_base64(path)
        self.assertEqual(read["content_base64"], "AAECAwQ=")

        target = WORKSPACE_DIR / path
        if target.exists():
            target.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
