"""
Mnemosyne - The Zero-Dependency AI Memory System

A native, sub-millisecond memory system for AI agents using SQLite.
No HTTP, no servers, no API keys — just Python and SQLite.

Example:
    >>> from mnemosyne import remember, recall
    >>> remember("User prefers dark mode", importance=0.9)
    >>> results = recall("user preferences")
"""

__version__ = "2.8.0"
__author__ = "Abdias J"
__license__ = "MIT"

# Lazy imports to allow mnemosyne.install to run without heavy deps
# (e.g. numpy is not yet installed during first-time setup)
_imported = False
_lazy_exports = {
    "Mnemosyne": (".core.memory", "Mnemosyne"),
    "remember": (".core.memory", "remember"),
    "recall": (".core.memory", "recall"),
    "get_context": (".core.memory", "get_context"),
    "get_stats": (".core.memory", "get_stats"),
    "forget": (".core.memory", "forget"),
    "update": (".core.memory", "update"),
}

def __getattr__(name: str):
    global _imported
    if name in _lazy_exports:
        mod_path, attr_name = _lazy_exports[name]
        mod = __import__(f"mnemosyne{mod_path}", fromlist=[attr_name])
        return getattr(mod, attr_name)
    raise AttributeError(f"module 'mnemosyne' has no attribute '{name}'")

__all__ = list(_lazy_exports.keys())


def _install_localhost_allowlist() -> None:
    """Restrict outbound urllib calls to localhost by default.

    Override with MNEMOSYNE_ALLOWED_HOSTS as comma-separated hostnames/IPs.
    """
    import os
    import urllib.request
    from urllib.parse import urlparse

    allowed = {
        h.strip().lower()
        for h in os.environ.get("MNEMOSYNE_ALLOWED_HOSTS", "localhost,127.0.0.1,::1").split(",")
        if h.strip()
    }
    if not allowed:
        allowed = {"localhost", "127.0.0.1", "::1"}

    if getattr(urllib.request.urlopen, "_mnemosyne_guarded", False):
        return

    _orig_urlopen = urllib.request.urlopen

    def _guarded_urlopen(url, *args, **kwargs):
        target = url.full_url if hasattr(url, "full_url") else str(url)
        host = (urlparse(target).hostname or "").lower().strip()
        if host not in allowed:
            raise ValueError(
                f"Outbound host '{host}' blocked by MNEMOSYNE_ALLOWED_HOSTS={sorted(allowed)}"
            )
        return _orig_urlopen(url, *args, **kwargs)

    _guarded_urlopen._mnemosyne_guarded = True  # type: ignore[attr-defined]
    urllib.request.urlopen = _guarded_urlopen


_install_localhost_allowlist()

# Conditionally expose MCP server if mcp package is installed
try:
    import mcp
    from mnemosyne.mcp_server import run_mcp_server
    _lazy_exports["run_mcp_server"] = (".mcp_server", "run_mcp_server")
    __all__.append("run_mcp_server")
except ImportError:
    pass  # MCP is optional — core works without it
