"""
Job Source Registry & Factory for managing multi-source job intelligence.
Allows registering, retrieving, filtering enabled sources, and disabling sources dynamically.
"""

import logging
from typing import Dict, List, Optional, Set

from app.config import Config
from app.sources.active_jobs_db import ActiveJobsDBJobSource
from app.sources.adzuna import AdzunaJobSource
from app.sources.arbeitnow import ArbeitnowJobSource
from app.sources.base import BaseJobSource
from app.sources.gmail import (
    CutshortAlertEmailSource,
    GlassdoorAlertEmailSource,
    HiristAlertEmailSource,
    IndeedAlertEmailSource,
    LinkedInAlertEmailSource,
    NaukriAlertEmailSource,
    UnstopAlertEmailSource,
    WellfoundAlertEmailSource,
    founditAlertEmailSource,
)
from app.sources.himalayas import HimalayasJobSource
from app.sources.internshala import InternshalaJobSource
from app.sources.jobicy import JobicyJobSource
from app.sources.jooble import JoobleJobSource
from app.sources.jsearch import JSearchJobSource
from app.sources.remoteok import RemoteOKJobSource
from app.sources.serpapi import SerpApiJobSource

logger = logging.getLogger(__name__)


class JobSourceRegistry:
    """
    Registry for managing registered job sources.
    Provides source lookup, enabled source discovery, dynamic disabling/enabling, and fault isolation.
    """

    def __init__(self):
        self._sources: Dict[str, BaseJobSource] = {}
        self._disabled_source_ids: Set[str] = set()

    @staticmethod
    def _clean_id(source_identifier: str) -> str:
        """Normalizes source identifier key."""
        return source_identifier.lower().strip().replace(" ", "_")

    def register(self, source: BaseJobSource):
        """
        Registers a job source instance.
        """
        source_id = self._clean_id(source.source_identifier)
        self._sources[source_id] = source
        logger.debug("Registered job source '%s' (id='%s').", source.name, source_id)

    def unregister(self, source_identifier: str):
        """
        Unregisters a source by identifier.
        """
        source_id = self._clean_id(source_identifier)
        self._sources.pop(source_id, None)

    def get_source(self, source_identifier: str) -> Optional[BaseJobSource]:
        """
        Retrieves a registered source by identifier or name.
        """
        source_id = self._clean_id(source_identifier)
        if source_id in self._sources:
            return self._sources[source_id]

        for s in self._sources.values():
            if self._clean_id(s.name) == source_id:
                return s
        return None

    def disable_source(self, source_identifier: str):
        """
        Disables a source in the registry.
        """
        source_id = self._clean_id(source_identifier)
        self._disabled_source_ids.add(source_id)

    def enable_source(self, source_identifier: str):
        """
        Re-enables a source in the registry.
        """
        source_id = self._clean_id(source_identifier)
        self._disabled_source_ids.discard(source_id)

    def is_source_enabled(self, source_identifier: str, config: Optional[Config] = None) -> bool:
        """
        Checks if a source is enabled in registry and config.
        """
        source = self.get_source(source_identifier)
        if not source:
            return False
        source_id = self._clean_id(source.source_identifier)
        if source_id in self._disabled_source_ids:
            return False
        return source.is_enabled(config)

    def list_sources(self) -> List[BaseJobSource]:
        """
        Returns all registered sources.
        """
        return list(self._sources.values())

    def list_enabled_sources(self, config: Optional[Config] = None) -> List[BaseJobSource]:
        """
        Returns all enabled sources according to registry state and application config.
        """
        enabled: List[BaseJobSource] = []
        for source_id, source in self._sources.items():
            if source_id in self._disabled_source_ids:
                continue
            if config and not source.is_enabled(config):
                continue
            enabled.append(source)
        return enabled


def create_default_source_registry(config: Optional[Config] = None) -> JobSourceRegistry:
    """
    Factory creating a JobSourceRegistry populated with existing job sources.
    """
    registry = JobSourceRegistry()
    config = config or Config()

    adzuna = AdzunaJobSource(
        app_id=config.adzuna_app_id,
        app_key=config.adzuna_app_key,
        country=config.adzuna_country,
    )
    registry.register(adzuna)

    internshala = InternshalaJobSource(
        request_delay_min=config.internshala_request_delay_min,
        request_delay_max=config.internshala_request_delay_max,
    )
    registry.register(internshala)

    linkedin_email = LinkedInAlertEmailSource(
        query=config.gmail_linkedin_query,
        query_limit=config.gmail_query_limit,
    )
    registry.register(linkedin_email)

    indeed_email = IndeedAlertEmailSource(
        query=config.gmail_indeed_query,
        query_limit=config.gmail_query_limit,
    )
    registry.register(indeed_email)

    naukri_email = NaukriAlertEmailSource(
        query=config.gmail_naukri_query,
        query_limit=config.gmail_query_limit,
    )
    registry.register(naukri_email)

    glassdoor_email = GlassdoorAlertEmailSource(
        query=config.gmail_glassdoor_query,
        query_limit=config.gmail_query_limit,
    )
    registry.register(glassdoor_email)

    unstop_email = UnstopAlertEmailSource(
        query=config.gmail_unstop_query,
        query_limit=config.gmail_query_limit,
    )
    registry.register(unstop_email)

    foundit_email = founditAlertEmailSource(
        query=config.gmail_foundit_query,
        query_limit=config.gmail_query_limit,
    )
    registry.register(foundit_email)

    cutshort_email = CutshortAlertEmailSource(
        query=config.gmail_cutshort_query,
        query_limit=config.gmail_query_limit,
    )
    registry.register(cutshort_email)

    hirist_email = HiristAlertEmailSource(
        query=config.gmail_hirist_query,
        query_limit=config.gmail_query_limit,
    )
    registry.register(hirist_email)

    wellfound_email = WellfoundAlertEmailSource(
        query=config.gmail_wellfound_query,
        query_limit=config.gmail_query_limit,
    )
    registry.register(wellfound_email)

    arbeitnow = ArbeitnowJobSource()
    registry.register(arbeitnow)

    remoteok = RemoteOKJobSource()
    registry.register(remoteok)

    jobicy = JobicyJobSource()
    registry.register(jobicy)

    himalayas = HimalayasJobSource()
    registry.register(himalayas)

    jooble = JoobleJobSource(api_key=config.jooble_api_key)
    registry.register(jooble)

    jsearch = JSearchJobSource(
        api_key=config.jsearch_api_key,
        rapidapi_host=config.jsearch_rapidapi_host,
    )
    registry.register(jsearch)

    serpapi = SerpApiJobSource(api_key=config.serpapi_key)
    registry.register(serpapi)

    active_jobs_db = ActiveJobsDBJobSource(
        api_key=config.active_jobs_db_api_key,
        rapidapi_host=config.active_jobs_db_rapidapi_host,
    )
    registry.register(active_jobs_db)

    return registry
