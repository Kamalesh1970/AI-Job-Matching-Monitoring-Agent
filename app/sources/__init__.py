"""
Job sources module.
"""

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
from app.sources.registry import JobSourceRegistry, create_default_source_registry
from app.sources.remoteok import RemoteOKJobSource
from app.sources.serpapi import SerpApiJobSource

__all__ = [
    "BaseJobSource",
    "AdzunaJobSource",
    "InternshalaJobSource",
    "LinkedInAlertEmailSource",
    "IndeedAlertEmailSource",
    "NaukriAlertEmailSource",
    "GlassdoorAlertEmailSource",
    "UnstopAlertEmailSource",
    "founditAlertEmailSource",
    "CutshortAlertEmailSource",
    "HiristAlertEmailSource",
    "WellfoundAlertEmailSource",
    "ArbeitnowJobSource",
    "RemoteOKJobSource",
    "JobicyJobSource",
    "HimalayasJobSource",
    "JoobleJobSource",
    "JSearchJobSource",
    "SerpApiJobSource",
    "JobSourceRegistry",
    "create_default_source_registry",
]

