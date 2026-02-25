from __future__ import annotations

import os


def ensure_dirs() -> None:
    os.makedirs(os.path.join("data", "logs"), exist_ok=True)

