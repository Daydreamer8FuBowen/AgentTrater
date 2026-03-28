from __future__ import annotations

"""Worker facade module.

Historically worker startup, factories and jobs lived in this module.
Now they are split across:
- worker.runtime
- worker.factory
- worker.jobs

This file keeps backward-compatible imports for existing callers/tests.
"""

from agent_trader.worker.factory import (
    build_kline_sync_service_factory,
    build_company_detail_sync_service_factory,
    create_scheduler,
)
from agent_trader.worker.jobs import register_kline_sync_jobs, register_company_detail_sync_jobs
from agent_trader.worker.runtime import WorkerRuntime, bootstrap_worker, main, run_worker_forever

__all__ = [
    "WorkerRuntime",
    "bootstrap_worker",
    "run_worker_forever",
    "main",
    "create_scheduler",
    "build_kline_sync_service_factory",
    "build_company_detail_sync_service_factory",
    "register_kline_sync_jobs",
    "register_company_detail_sync_jobs",
]
