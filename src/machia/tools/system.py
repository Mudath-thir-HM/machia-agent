"""Read-only system info tool."""
from __future__ import annotations
import platform
import shutil
from .spec import ToolSpec


def sys_info() -> dict:
    """Return basic info about this machine."""
    total, used, free = shutil.disk_usage("C:\\")
    return {
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "cpu_cores": __import__("os").cpu_count(),
        "disk_total_gb": round(total / (1024 ** 3), 1),
        "disk_free_gb": round(free / (1024 ** 3), 1),
    }


SYS_INFO = ToolSpec(
    name="sys_info",
    description="Get information about this computer: OS, CPU cores, disk space.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    function=sys_info,
    risk="low",
)