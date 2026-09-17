"""
Health Service for checking pipeline heartbeat, health status evaluation,
and deduplicated Telegram operational alerts.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import sqlite3

from app.config import Config
from app.db.database import (
    get_last_pipeline_run,
    get_last_successful_pipeline_run,
    get_unresolved_health_alert,
    record_health_alert,
    resolve_health_alerts,
)
from app.services.telegram_notifier import TelegramNotifier

logger = logging.getLogger("app.services.health_service")


class HealthStatus:
    """Operational health status constants."""

    HEALTHY = "HEALTHY"
    STALE = "STALE"
    FAILED = "FAILED"


@dataclass
class HealthEvaluationResult:
    """Detailed health evaluation status."""

    status: str
    last_run_time: Optional[str] = None
    last_successful_run_time: Optional[str] = None
    minutes_since_last_success: Optional[float] = None
    message: str = ""


class HealthService:
    """
    Service for heartbeat health monitoring and operational alert dispatching.
    """

    def __init__(self, config: Optional[Config] = None):
        """Initializes HealthService with application configuration."""
        self.config = config

    def _parse_iso_datetime(self, dt_str: str) -> datetime:
        """Parses ISO timestamp string into a timezone-aware datetime object."""
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def evaluate_health(
        self,
        conn: sqlite3.Connection,
        config: Optional[Config] = None,
        reference_time: Optional[datetime] = None,
    ) -> HealthEvaluationResult:
        """
        Evaluates current operational health based on last successful pipeline run timestamp.

        Args:
            conn: SQLite database connection.
            config: Application Config object.
            reference_time: Optional reference datetime (defaults to UTC now).

        Returns:
            HealthEvaluationResult: Health status evaluation.
        """
        cfg = config or self.config
        if not cfg:
            raise ValueError("Configuration object is required for health evaluation.")

        if not reference_time:
            reference_time = datetime.now(timezone.utc)
        elif reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        last_run = get_last_pipeline_run(conn)
        last_success = get_last_successful_pipeline_run(conn)

        last_run_time = last_run["started_at"] if last_run else None

        if not last_success:
            # No successful pipeline run has ever completed
            return HealthEvaluationResult(
                status=HealthStatus.STALE,
                last_run_time=last_run_time,
                last_successful_run_time=None,
                minutes_since_last_success=None,
                message="No successful pipeline run recorded in history.",
            )

        success_timestamp_str = (
            last_success.get("finished_at") or last_success.get("started_at")
        )
        if not success_timestamp_str:
            return HealthEvaluationResult(
                status=HealthStatus.STALE,
                last_run_time=last_run_time,
                last_successful_run_time=None,
                minutes_since_last_success=None,
                message="Invalid timestamp on last successful pipeline run.",
            )

        success_dt = self._parse_iso_datetime(success_timestamp_str)
        elapsed_minutes = (reference_time - success_dt).total_seconds() / 60.0

        timeout = float(cfg.heartbeat_timeout_minutes)

        if elapsed_minutes > timeout:
            status = HealthStatus.STALE
            msg = (
                f"Pipeline is stale. Elapsed: {elapsed_minutes:.1f}m (timeout: {timeout:.1f}m)."
            )
        elif last_run and last_run.get("status") == "FAILED" and elapsed_minutes > cfg.scheduler_interval_minutes:
            status = HealthStatus.FAILED
            msg = f"Last pipeline run failed and elapsed time is {elapsed_minutes:.1f}m."
        else:
            status = HealthStatus.HEALTHY
            msg = f"Pipeline is healthy. Last successful run was {elapsed_minutes:.1f}m ago."

        return HealthEvaluationResult(
            status=status,
            last_run_time=last_run_time,
            last_successful_run_time=success_timestamp_str,
            minutes_since_last_success=elapsed_minutes,
            message=msg,
        )

    def check_and_alert_health(
        self,
        conn: sqlite3.Connection,
        config: Optional[Config] = None,
        notifier: Optional[TelegramNotifier] = None,
        reference_time: Optional[datetime] = None,
    ) -> HealthEvaluationResult:
        """
        Evaluates health and dispatches deduplicated Telegram operational alerts when stale.
        """
        cfg = config or self.config
        if not cfg:
            raise ValueError("Configuration object is required for health alert check.")

        result = self.evaluate_health(
            conn=conn, config=cfg, reference_time=reference_time
        )

        if result.status in (HealthStatus.STALE, HealthStatus.FAILED):
            # Check if an unresolved alert has already been sent
            unresolved = get_unresolved_health_alert(conn, alert_type="stale_pipeline")
            if not unresolved:
                logger.warning(
                    "Health evaluation status is %s. Preparing Telegram operational alert...",
                    result.status,
                )
                if notifier is None:
                    notifier = TelegramNotifier(config=cfg)

                last_success_display = (
                    result.last_successful_run_time or "Never / None"
                )
                alert_text = (
                    "PIPELINE HEALTH ALERT\n\n"
                    "The job monitoring pipeline has not completed successfully within the configured heartbeat window.\n\n"
                    f"Last successful run:\n{last_success_display}\n\n"
                    f"Current status:\n{result.status}\n\n"
                    "Please check the monitoring service."
                )

                sent = notifier.send_message(alert_text)
                record_health_alert(conn, alert_type="stale_pipeline")
                logger.info(
                    "Recorded new stale_pipeline health alert record (Telegram delivered: %s).",
                    sent,
                )
        elif result.status == HealthStatus.HEALTHY:
            resolved_count = resolve_health_alerts(conn, alert_type="stale_pipeline")
            if resolved_count > 0:
                logger.info(
                    "Pipeline status recovered to HEALTHY. Resolved %d active health alert(s).",
                    resolved_count,
                )

        return result
