"""ARQ worker entry point.

Launch the worker with::

    arq app.workers.entrypoint.WorkerSettings

:class:`~app.workers.scheduler.WorkerSettings` populates its ``functions``
and ``cron_jobs`` lazily via :meth:`~app.workers.scheduler.WorkerSettings.configure`
so that importing the web app never pulls in arq. The arq CLI, however, reads
those attributes off the class as soon as it imports the settings module — if
``configure()`` hasn't run yet they're empty and arq aborts with "at least one
function or cron_job must be registered".

Importing *this* module calls ``configure()`` first, then re-exports the ready
class, so ``arq app.workers.entrypoint.WorkerSettings`` just works. The web app
still imports ``scheduler`` (not this module), so the lazy-init contract holds.

It also imports every domain's models. Unlike the web app, the worker never
imports the routers that would pull them in transitively, so without this any
task touching the DB dies in mapper configuration with ``expression 'Account'
failed to locate a name`` — which is how Instagram posts silently sat in
``pending``.
"""

from __future__ import annotations

from app.core.models_registry import import_all_models
from app.workers.scheduler import WorkerSettings

import_all_models()
WorkerSettings.configure()

__all__ = ["WorkerSettings"]
