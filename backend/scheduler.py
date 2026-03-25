"""
Background scheduler — periodically fetches prices for all held ETFs.
Uses APScheduler with async support.
"""

import logging
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .prices import fetch_all_holdings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_price_update():
    """Job: fetch prices for all tickers in portfolio."""
    logger.info("Scheduled price update starting...")
    try:
        results = await fetch_all_holdings()
        success = sum(1 for r in results if not r.get("error"))
        failed = sum(1 for r in results if r.get("error"))
        logger.info(f"Price update complete: {success} succeeded, {failed} failed")
    except Exception as e:
        logger.error(f"Scheduled price update failed: {e}")


def start_scheduler():
    """Start the background scheduler."""
    interval_hours = int(os.environ.get("UPDATE_INTERVAL", "6"))

    scheduler.add_job(
        scheduled_price_update,
        trigger=IntervalTrigger(hours=interval_hours),
        id="price_update",
        name="Fetch ETF prices",
        replace_existing=True,
        max_instances=1,
    )

    # Also run once at startup (with a small delay to let the app initialize)
    scheduler.add_job(
        scheduled_price_update,
        trigger="date",
        id="price_update_startup",
        name="Initial price fetch",
    )

    scheduler.start()
    logger.info(f"Scheduler started: updating every {interval_hours} hours")


def stop_scheduler():
    """Shutdown the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
