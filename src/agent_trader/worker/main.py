from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

# 定时器
def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    return scheduler
