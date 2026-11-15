"""Jobs enqueued under a fixed id, to fold a burst into one run, must keep
no result: ARQ refuses an id while its result lives (an hour by default), so
the next burst after a run would be dropped without a word."""

import pytest
from arq.worker import Function

from app.workers.scheduler import WorkerSettings


@pytest.mark.parametrize("name", ["sync_meta_catalog_task"])
def test_a_job_that_folds_bursts_can_run_again_right_after(name: str) -> None:
    jobs = {f.name: f for f in WorkerSettings._functions() if isinstance(f, Function)}
    assert jobs[name].keep_result_s == 0
