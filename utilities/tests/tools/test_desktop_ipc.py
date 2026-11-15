import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DESKTOP = ROOT / "desktop-app" / "src"

# Evaluates each preload with a stub `require` that only allows 'electron' —
# exactly what Electron's sandbox permits — and returns the channel map it built.
_PROBE = r"""
const fs = require('fs'); const vm = require('vm');
const shared = require(process.argv[1]);
const out = {};
for (const file of process.argv.slice(2)) {
  let exposed = null;
  const electron = { contextBridge: { exposeInMainWorld: (_n, api) => { exposed = api } },
                     ipcRenderer: { invoke: (c) => c, on() {}, removeListener() {} } };
  const sandboxRequire = (name) => {
    if (name === 'electron') return electron;
    throw new Error(`sandboxed preload cannot require ${name}`);
  };
  const code = fs.readFileSync(file, 'utf8') + '\n;__IPC__ = IPC;';
  const ctx = { require: sandboxRequire, console, __IPC__: null };
  vm.runInNewContext(code, ctx, { filename: file });
  out[file] = { ipc: ctx.__IPC__, exposed: exposed !== null };
}
console.log(JSON.stringify({ shared, out }));
"""


@unittest.skipUnless(shutil.which("node"), "node is required")
class DesktopPreloadTests(unittest.TestCase):
    def test_preloads_load_under_sandbox_and_match_shared_channels(self) -> None:
        preloads = [str(DESKTOP / "preload" / "main-preload.js"), str(DESKTOP / "preload" / "settings-preload.js")]
        result = subprocess.run(
            ["node", "-e", _PROBE, str(DESKTOP / "shared" / "ipc-channels.js"), *preloads],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        shared = data["shared"]
        for file, info in data["out"].items():
            with self.subTest(preload=Path(file).name):
                self.assertTrue(info["exposed"], "preload did not expose its API")
                for group, channels in info["ipc"].items():
                    for key, value in channels.items():
                        self.assertEqual(shared[group][key], value, f"{group}.{key} drifted from shared/ipc-channels.js")


if __name__ == "__main__":
    unittest.main(verbosity=2)
