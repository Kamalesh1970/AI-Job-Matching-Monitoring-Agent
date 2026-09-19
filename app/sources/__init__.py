"""
Job sources module.
"""

from app.sources.adzuna import AdzunaJobSource
from app.sources.arbeitnow import ArbeitnowJobSource
from app.sources.base import BaseJobSource
from app.sources.gmail import (
    GlassdoorAlertEmailSource,
    IndeedAlertEmailSource,
    LinkedInAlertEmailSource,
    NaukriAlertEmailSource,
)
from app.sources.himalayas import HimalayasJobSource
from app.sources.internshala import InternshalaJobSource
from app.sources.jobicy import JobicyJobSource
from app.sources.jooble import JoobleJobSource
from app.sources.registry import JobSourceRegistry, create_default_source_registry
from app.sources.remoteok import RemoteOKJobSource

__all__ = [
    "BaseJobSource",
    "AdzunaJobSource",
    "InternshalaJobSource",
    "LinkedInAlertEmailSource",
    "IndeedAlertEmailSource",
    "NaukriAlertEmailSource",
    "GlassdoorAlertEmailSource",
    "ArbeitnowJobSource",
    "RemoteOKJobSource",
    "JobicyJobSource",
    "HimalayasJobSource",
    "JoobleJobSource",
    "JobSourceRegistry",
    "create_default_source_registry",
]
