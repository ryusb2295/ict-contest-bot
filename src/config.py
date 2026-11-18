"""Configuration management for ICT Contest Bot."""
import os

# Clear problematic SSLKEYLOGFILE if set by host OS
if "SSLKEYLOGFILE" in os.environ:
    try:
        del os.environ["SSLKEYLOGFILE"]
    except Exception:
        pass

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

def _load_env_file(path: Path) -> None:
    """Built-in resilient parser for .env files that works without external dependencies."""
    if not path.is_file():
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                # Do not load placeholder strings as real values
                if k and k not in os.environ and not v.startswith("your_") and v != "":
                    os.environ[k] = v
    except Exception:
        pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Resiliently parse .env, .env.local, or .env.example
_load_env_file(Path(".env").resolve())
_load_env_file(Path(".env.local").resolve())
_load_env_file(Path(".env.example").resolve())


@dataclass
class Config:
    """Application configuration container."""

    discord_webhook_url: str = field(
        default_factory=lambda: os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    )
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip()
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    )
    timezone: str = field(
        default_factory=lambda: os.getenv("TZ", "Asia/Seoul").strip()
    )
    alert_days: List[int] = field(
        default_factory=lambda: [
            int(x.strip())
            for x in os.getenv("ALERT_DAYS", "7,3,1").split(",")
            if x.strip().isdigit()
        ]
    )
    data_file: Path = field(
        default_factory=lambda: Path(
            os.getenv("DATA_FILE", "data/contests.json")
        ).resolve()
    )
    request_timeout: int = 15
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 ICTContestBot/1.0"
    )

    @property
    def has_webhook(self) -> bool:
        return bool(self.discord_webhook_url)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)


# Global default configuration instance
config = Config()
