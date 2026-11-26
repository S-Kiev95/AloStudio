"""The voice process (F7 paso 3): Pipecat and Gemini Live answer the WhatsApp
calls an inbox gives its voice AI.

It runs apart from the API (``python -m app.voice``), with its own extra
dependencies (``uv sync --group voice``), and only listens on localhost.
The API decides which calls it answers and talks to Meta; this process
only holds the audio (WebRTC with Meta) and the conversation with Gemini.
See :mod:`app.domains.calls.voice`.
"""
