"""Job queue and processing utilities."""
import json
from pathlib import Path
from typing import Optional


def get_config() -> dict:
    config_file = Path.home() / ".appy4me" / "config.json"
    if config_file.exists():
        return json.loads(config_file.read_text())
    return {}


def save_config(config: dict):
    config_dir = Path.home() / ".appy4me"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps(config, indent=2))
