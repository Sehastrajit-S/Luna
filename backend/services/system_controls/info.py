"""System information."""
import re
import shutil
from pathlib import Path

from backend.services.system_controls.helpers import IS_MAC, IS_WINDOWS, IS_LINUX, PLATFORM, _run


def _cpu_name() -> str:
    """The CPU's marketing name ("AMD Ryzen 7 5800X"), not platform.processor()'s family code."""
    try:
        if IS_WINDOWS:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        if IS_MAC:
            rc, out = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
            return out.strip() if rc == 0 else ""
        if IS_LINUX:
            m = re.search(r"model name\s*:\s*(.+)", Path("/proc/cpuinfo").read_text())
            return m.group(1).strip() if m else ""
    except Exception:
        pass
    return ""


def _gpus() -> list[str]:
    if not shutil.which("nvidia-smi"):
        return []
    rc, out = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
    return [line.strip() for line in out.splitlines() if line.strip()] if rc == 0 else []


def get_system_info() -> dict:
    """OS, CPU, RAM, disk, battery and GPU — read directly (psutil / OS APIs), not
    through PowerShell, which timed out under load and never reported the CPU."""
    import platform as _p
    import psutil

    info: dict = {
        "os":      PLATFORM,
        "version": _p.version(),
        "machine": _p.machine(),
        "node":    _p.node(),
    }
    cpu = _cpu_name()
    if cpu:
        info["cpu"] = cpu
    info["cpu_cores"] = psutil.cpu_count(logical=False)
    info["cpu_threads"] = psutil.cpu_count(logical=True)

    mem = psutil.virtual_memory()
    info["ram_gb"] = round(mem.total / 1_073_741_824, 1)
    info["ram_free_gb"] = round(mem.available / 1_073_741_824, 1)

    try:
        disk = psutil.disk_usage(str(Path.home().anchor or "/"))
        info["disk_gb"] = round(disk.total / 1_073_741_824)
        info["disk_free_gb"] = round(disk.free / 1_073_741_824)
    except OSError:
        pass

    try:
        battery = psutil.sensors_battery()
    except (AttributeError, NotImplementedError):
        battery = None
    if battery is not None:
        info["battery_pct"] = round(battery.percent)
        info["plugged_in"] = bool(battery.power_plugged)

    gpus = _gpus()
    if gpus:
        info["gpu"] = gpus
    return info
