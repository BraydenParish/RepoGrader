"""JSON schema loader."""
from __future__ import annotations

import json
from importlib import resources
from typing import Any, Dict


with resources.files(__package__).joinpath("schema.json").open("r", encoding="utf-8") as fh:
    SCHEMA: Dict[str, Any] = json.load(fh)

