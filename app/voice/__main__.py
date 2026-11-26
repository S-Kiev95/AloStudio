"""``python -m app.voice``: start the voice process on localhost.

``VOICE_PORT`` picks the port (8010 by default); the API reaches it at
``VOICE_SERVICE_URL`` with ``VOICE_SERVICE_TOKEN``.
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "app.voice.server:app",
        host="127.0.0.1",
        port=int(os.environ.get("VOICE_PORT", "8010")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
