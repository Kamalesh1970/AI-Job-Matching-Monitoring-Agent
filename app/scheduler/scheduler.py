"""
Dedicated APScheduler service for periodic job monitoring execution.
Handles job registration, misfire behavior, overlap protection, and graceful shutdown.
"""

import logging
import signal
import sys
import time
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import Config
from app.services.pipeline_service import PipelineService

logger = logging.getLogger("app.scheduler.scheduler")


class PipelineScheduler:
    """
    Service wrapper around APScheduler BackgroundScheduler for job monitoring daemon.
    """

    JOB_ID = "scheduled_monitoring_pipeline_job"

    def __init__(self, config: Config, pipeline_service: Optional[PipelineService] = None):
        """Initializes PipelineScheduler with application configuration."""
        self.config = config
        self.pipeline_service = pipeline_service or PipelineService(config=self.config)
        self.scheduler = BackgroundScheduler(timezone="UTC")
        self._is_running = False

    def scheduled_job_wrapper(self):
        """Wrapper method invoked by APScheduler to run the pipeline."""
        logger.info("APScheduler trigger fired: executing scheduled monitoring pipeline...")
        try:
            summary = self.pipeline_service.run_monitoring_pipeline(config=self.config)
            logger.info("Scheduled pipeline completed with status: %s", summary.status)
        except Exception as e:
            logger.error("Unexpected exception in scheduled pipeline wrapper: %s", str(e), exc_info=True)

    def register_scheduled_job(self):
        """Registers the monitoring pipeline job in APScheduler with overlap & misfire protection."""
        if self.scheduler.get_job(self.JOB_ID):
            logger.info("Job '%s' already registered. Skipping duplicate registration.", self.JOB_ID)
            return

        interval_minutes = max(1, self.config.scheduler_interval_minutes)

        self.scheduler.add_job(
            func=self.scheduled_job_wrapper,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=self.JOB_ID,
            name="AI Job-Matching & Monitoring Scheduled Pipeline",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=900,
            replace_existing=True,
        )
        logger.info(
            "Registered scheduled job '%s' with interval = %d minute(s), max_instances = 1, coalesce = True.",
            self.JOB_ID,
            interval_minutes,
        )

    def start(self, block: bool = True):
        """
        Starts the scheduler daemon process.

        Args:
            block: If True, blocks the main thread in a loop until SIGINT/SIGTERM is received.
        """
        if not self.config.scheduler_enabled:
            logger.warning("SCHEDULER_ENABLED is False in config. Scheduler will not start.")
            return

        self.register_scheduled_job()

        if not self.scheduler.running:
            self.scheduler.start()
            self._is_running = True
            logger.info("APScheduler started successfully.")

            job = self.scheduler.get_job(self.JOB_ID)
            if job and job.next_run_time:
                logger.info("Next scheduled pipeline run set for: %s", job.next_run_time)

        # Handle startup execution if configured
        if self.config.run_on_startup:
            logger.info("RUN_ON_STARTUP is True. Triggering immediate initial pipeline run...")
            self.scheduled_job_wrapper()

        if block:
            self._setup_signal_handlers()
            logger.info("Scheduler daemon running. Press Ctrl+C or send SIGTERM to stop.")
            try:
                while self._is_running:
                    time.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                self.shutdown()

    def shutdown(self):
        """Gracefully shuts down the scheduler daemon."""
        if self._is_running:
            logger.info("Initiating graceful shutdown of PipelineScheduler...")
            self._is_running = False
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
            logger.info("PipelineScheduler shutdown completed cleanly.")

    def _setup_signal_handlers(self):
        """Attaches handlers for SIGINT and SIGTERM OS signals."""
        def handle_signal(sig, frame):
            sig_name = "SIGINT" if sig == signal.SIGINT else "SIGTERM"
            logger.info("Received OS signal %s (%d). Triggering graceful exit...", sig_name, sig)
            self.shutdown()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, handle_signal)
            signal.signal(signal.SIGTERM, handle_signal)
        except (ValueError, AttributeError):
            # Signal handling might not be supported in non-main threads or certain environments
            pass
