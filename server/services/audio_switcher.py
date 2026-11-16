"""
Windows default audio output device switcher.
Uses the undocumented IPolicyConfig COM interface (works on Windows 10/11).
"""
import json
import warnings
from pathlib import Path

from server.config import DATA_DIR

# Suppress pycaw COMError warnings for missing properties
warnings.filterwarnings("ignore", message="COMError")

_PREFS_FILE = DATA_DIR / "audio_prefs.json"
_POLICY_CLSID = "{870AF99C-171D-4F9E-AF0D-E63DF40C2BC9}"
_POLICY_IID   = "{F8679F50-850A-41CF-9C72-430F290290C8}"

# Devices to hide from the picker (too noisy / virtual)
_HIDE_KEYWORDS = (
    "steam streaming", "spacedesk", "dubbing virtual",
    "oculus virtual", "nvidia broadcast", "nvidia output",
    "high definition audio device", "hdmi", "s/pdif",
    "digital audio",
)


def _policy():
    """Return an IPolicyConfig COM instance."""
    from comtypes import GUID, CLSCTX_ALL, IUnknown, STDMETHOD, HRESULT, c_wchar_p, c_uint
    import comtypes.client

    class IPolicyConfig(IUnknown):
        _iid_ = GUID(_POLICY_IID)
        _methods_ = [
            STDMETHOD(HRESULT, "GetMixFormat",        []),
            STDMETHOD(HRESULT, "GetDeviceFormat",     []),
            STDMETHOD(HRESULT, "ResetDeviceFormat",   []),
            STDMETHOD(HRESULT, "SetDeviceFormat",     []),
            STDMETHOD(HRESULT, "GetProcessingPeriod", []),
            STDMETHOD(HRESULT, "SetProcessingPeriod", []),
            STDMETHOD(HRESULT, "GetShareMode",        []),
            STDMETHOD(HRESULT, "SetShareMode",        []),
            STDMETHOD(HRESULT, "GetPropertyValue",    []),
            STDMETHOD(HRESULT, "SetPropertyValue",    []),
            STDMETHOD(HRESULT, "SetDefaultEndpoint",  [c_wchar_p, c_uint]),
            STDMETHOD(HRESULT, "SetEndpointVisibility",[]),
        ]

    return comtypes.client.CreateObject(GUID(_POLICY_CLSID), interface=IPolicyConfig, clsctx=CLSCTX_ALL)


def list_output_devices() -> list[dict]:
    """Return output devices suitable for the picker."""
    from pycaw.pycaw import AudioUtilities
    all_devs = AudioUtilities.GetAllDevices()
    out = []
    for d in all_devs:
        if not d.FriendlyName:
            continue
        if not d.id.startswith("{0.0.0."):
            continue  # skip input devices
        name_lower = d.FriendlyName.lower()
        if any(k in name_lower for k in _HIDE_KEYWORDS):
            continue
        out.append({"id": d.id, "name": d.FriendlyName})
    # Deduplicate by id
    seen = set()
    result = []
    for item in out:
        if item["id"] not in seen:
            seen.add(item["id"])
            result.append(item)
    return result


def get_default_device_id() -> str | None:
    """Read the saved default device id from prefs file."""
    try:
        return json.loads(_PREFS_FILE.read_text())["device_id"]
    except Exception:
        return None


def set_default_device(device_id: str) -> bool:
    """Set the Windows default audio output to device_id (all three roles)."""
    try:
        policy = _policy()
        for role in (0, 1, 2):  # eConsole, eMultimedia, eCommunications
            policy.SetDefaultEndpoint(device_id, role)
        _PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PREFS_FILE.write_text(json.dumps({"device_id": device_id}))
        return True
    except Exception as e:
        print(f"[audio] set_default_device failed: {e}")
        return False
