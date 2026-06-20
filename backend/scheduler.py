import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import get_user_analyses, add_spend_history
from aws_scanner import get_actual_spend

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def track_drift_job():
    """
    Daily background job to track cost drift.
    Fetches actual spend from AWS CE and saves it to DB alongside the latest AI predicted spend.
    """
    logger.info("Running daily drift tracking job...")
    try:
        # In a real app, we'd loop over active user accounts/regions.
        # For this MVP, we assume a single environment and fetch CE data.
        actual_spend_data = get_actual_spend()
        
        if not actual_spend_data:
            logger.warning("No actual spend data returned from Cost Explorer.")
            return

        # Fetch the most recent analysis prediction to use as our "predicted" spend
        # Assuming user_id=1 for the demo MVP
        analyses = get_user_analyses(user_id=1, limit=1)
        predicted_spend = 0.0
        if analyses:
            predicted_spend = float(analyses[0].get("predicted_monthly_spend", 0.0))

        # Insert today's actual and predicted spend into the history table
        for data_point in actual_spend_data:
            add_spend_history(
                account_id="default_account", # In production, extract from AWS STS
                date_str=data_point["date"],
                actual_spend=data_point["actual_spend"],
                predicted_spend=predicted_spend
            )
            
        logger.info(f"Drift tracking job completed. Inserted {len(actual_spend_data)} records.")
    except Exception as e:
        logger.error(f"Error in drift tracking job: {e}")

def start_scheduler():
    """Initialize and start the background scheduler."""
    scheduler.add_job(track_drift_job, 'interval', hours=24)
    scheduler.start()
    logger.info("Background scheduler started. Drift tracking job scheduled every 24 hours.")
