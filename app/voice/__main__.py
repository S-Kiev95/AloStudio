"""``python -m app.voice``: start the voice process on localhost.

``VOICE_PORT`` picks the port (8010 by default); the API reaches it at
``VOICE_SERVICE_URL`` with ``VOICE_SERVICE_TOKEN``. ``VOICE_LOG_LEVEL``
(INFO by default) sets Pipecat's log: at DEBUG it writes each call's whole
instructions, the business's data included.
"""

from __future__ import annotations

import os
import sys

import uvicorn
from loguru import logger


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level=os.environ.get("VOICE_LOG_LEVEL", "INFO"))
    uvicorn.run(
        "app.voice.server:app",
        host="127.0.0.1",
        port=int(os.environ.get("VOICE_PORT", "8010")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
