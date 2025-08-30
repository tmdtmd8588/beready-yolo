# -*- coding: utf-8 -*-
# Created by rad-haha(absinthe6),안시은 ,2025
# Part of Team Project: [beready]
# License: MIT
"""
scheduler.py
- APScheduler로 매주 월요일 오전 06:00(KST) 1회 최신 식단표 크롤링
- 별도 프로세스로 실행:  python scheduler.py
"""

import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from crawler import crawl_once  # 크롤링 함수 재사용

async def crawl_job():
    # 블로킹 I/O는 스레드로
    await asyncio.to_thread(crawl_once)

async def main():
    scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
    # 매주 월요일 06:00
    scheduler.add_job(
        lambda: asyncio.create_task(crawl_job()),
        CronTrigger(day_of_week="mon", hour=6, minute=0),
        id="weekly_monday_crawl",
        coalesce=True,
        misfire_grace_time=3600,
        max_instances=1,
        replace_existing=True,
    )
    scheduler.start()
    print("[SCHED] started (runs every Monday 06:00 KST)")
    # 무한 대기
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
