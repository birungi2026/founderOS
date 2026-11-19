import hashlib
import json
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

Text = Annotated[str, Field(min_length=1, max_length=1500)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BrandInput(StrictModel):
    founder_name: str = Field(min_length=2, max_length=100)
    website_url: HttpUrl | None = None
    story: str = Field(min_length=20, max_length=4000)
    expertise: list[Text] = Field(min_length=1, max_length=8)
    voice: str = Field(min_length=3, max_length=500)
    positioning: str = Field(min_length=10, max_length=1500)
    content_pillars: list[Text] = Field(min_length=1, max_length=5)
    proof_points: list[Text] = Field(default_factory=list, max_length=10)
    avoid_topics: list[Text] = Field(default_factory=list, max_length=10)
    base_version_id: str | None = None


class CampaignInput(StrictModel):
    goal: str = Field(min_length=10, max_length=1000)
    week_start: date
    launch_date: date
    research_mode: Literal["automatic", "manual"] = "automatic"
    cadence: Literal["weekly", "daily"] = "weekly"
    posts_per_day: int = Field(default=1, ge=1, le=5)
    research_only: bool = False


class Opportunity(StrictModel):
    angle: Text
    audience_fit: Text
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    uncertainty: Text


class ProspectCandidate(StrictModel):
    name: str = Field(min_length=2, max_length=200)
    source_id: str
    qualification: Text
    unknowns: Text


class CompetitorFinding(StrictModel):
    company: str = Field(min_length=2, max_length=200)
    source_id: str
    observation: Text
    uncertainty: Text


class PlatformStrategy(StrictModel):
    platform: Literal["instagram", "tiktok", "facebook", "linkedin"]
    ranking_summary: Text
    experiment: Text
    success_metric: Text
    evidence_ids: list[str] = Field(min_length=1, max_length=10)
    uncertainty: Text


class ResearchArtifact(StrictModel):
    platform_strategies: list[PlatformStrategy] = Field(default_factory=list, max_length=4)
    opportunities: list[Opportunity] = Field(min_length=1, max_length=5)
    prospects: list[ProspectCandidate] = Field(default_factory=list, max_length=5)
    company_understanding: str = Field(default="", max_length=2000)
    differentiation_hypothesis: str = Field(default="", max_length=2000)
    competitor_observations: list[CompetitorFinding] = Field(default_factory=list, max_length=5)


class CalendarEntry(StrictModel):
    day: int = Field(ge=1, le=7)
    title: str = Field(min_length=2, max_length=200)
    channel: Literal["linkedin", "outreach"]
    content: str = Field(min_length=10, max_length=6000)
    hypothesis: Text
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class GrowthArtifact(StrictModel):
    objective: Text
    experiment: Text
    success_metric: Text
    calendar: list[CalendarEntry] = Field(min_length=7, max_length=7)

    @field_validator("calendar")
    @classmethod
    def seven_days(cls, value):
        if {entry.day for entry in value} != set(range(1, 8)):
            raise ValueError("Calendar must contain each day from 1 through 7 exactly once")
        return sorted(value, key=lambda entry: entry.day)


class DailyGrowthArtifact(StrictModel):
    objective: Text
    experiment: Text
    success_metric: Text
    calendar: list[CalendarEntry] = Field(min_length=1, max_length=5)

    @field_validator("calendar")
    @classmethod
    def today_only(cls, value):
        if any(entry.day != 1 for entry in value):
            raise ValueError("Daily run must produce only day one")
        return value


class Scene(StrictModel):
    duration_seconds: int = Field(ge=2, le=20)
    narration: str = Field(min_length=2, max_length=400)
    caption: str = Field(min_length=2, max_length=120)
    visual: str = Field(min_length=2, max_length=300)


class VideoArtifact(StrictModel):
    title: str = Field(min_length=2, max_length=200)
    hook: Text
    scenes: list[Scene] = Field(min_length=2, max_length=8)
    call_to_action: Text

    @field_validator("scenes")
    @classmethod
    def duration(cls, value):
        if not 15 <= sum(scene.duration_seconds for scene in value) <= 60:
            raise ValueError("Video script must be between 15 and 60 seconds")
        return value


class LaunchItem(StrictModel):
    phase: Literal["pre_launch", "launch_day", "follow_up"]
    title: str = Field(min_length=3, max_length=500)
    days_from_launch: int = Field(ge=-30, le=30)


class LaunchArtifact(StrictModel):
    message: Text
    tasks: list[LaunchItem] = Field(min_length=3, max_length=15)

    @field_validator("tasks")
    @classmethod
    def phases_match_dates(cls, value):
        if {task.phase for task in value} != {"pre_launch", "launch_day", "follow_up"}:
            raise ValueError("Launch plan must cover pre-launch, launch day and follow-up")
        for task in value:
            if (
                (task.phase == "pre_launch" and task.days_from_launch >= 0)
                or (task.phase == "launch_day" and task.days_from_launch != 0)
                or (task.phase == "follow_up" and task.days_from_launch <= 0)
            ):
                raise ValueError("Task date does not match its launch phase")
        return value


class RevisionInput(StrictModel):
    expected_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    content: str = Field(min_length=10, max_length=6000)
    planned_date: date


class TaskDecision(StrictModel):
    completed: bool


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def revision_hash(draft):
    return digest(
        {
            "content": draft.content,
            "channel": draft.channel,
            "planned_date": draft.generation.get("planned_date"),
            "version": draft.revision_number,
        }
    )
