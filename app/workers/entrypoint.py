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
"""

from __future__ import annotations

from app.workers.scheduler import WorkerSettings

WorkerSettings.configure()

__all__ = ["WorkerSettings"]
