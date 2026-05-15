from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class TimePeriod:
    name: str
    start_hour: int
    end_hour: int
    days_of_week: list[int]


@dataclass
class ScheduleEntry:
    time: datetime
    action: str
    sources: list[str]


class Scheduler:
    PRESETS = {
        "always_on": ([TimePeriod("all", 0, 23, [0, 1, 2, 3, 4, 5, 6])], {"crawl": True, "analyze": True, "push": True}),
        "morning_evening": (
            [
                TimePeriod("morning", 7, 9, [0, 1, 2, 3, 4, 5, 6]),
                TimePeriod("evening", 19, 22, [0, 1, 2, 3, 4, 5, 6]),
            ],
            {"crawl": True, "analyze": True, "push": True},
        ),
        "office_hours": (
            [
                TimePeriod("workday", 9, 18, [1, 2, 3, 4, 5]),
            ],
            {"crawl": True, "analyze": True, "push": True},
        ),
        "night_owl": (
            [
                TimePeriod("late_night", 22, 3, [0, 1, 2, 3, 4, 5, 6]),
            ],
            {"crawl": True, "analyze": True, "push": True},
        ),
    }

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._load_preset()

    def _load_preset(self):
        preset_name = self.config.get("preset", "always_on")
        if preset_name in self.PRESETS:
            self.periods, self.actions = self.PRESETS[preset_name]
        else:
            self.periods = self.PRESETS["always_on"][0]
            self.actions = self.PRESETS["always_on"][1]

    def is_active(self, current_time: Optional[datetime] = None) -> bool:
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        current_hour = current_time.hour
        current_day = current_time.weekday()

        for period in self.periods:
            if current_day in period.days_of_week:
                if period.start_hour <= current_hour < period.end_hour:
                    return True
                if period.start_hour > period.end_hour:
                    if current_hour >= period.start_hour or current_hour < period.end_hour:
                        return True

        return False

    def get_next_run_times(self, current_time: Optional[datetime] = None, count: int = 5) -> list[datetime]:
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        times = []
        for period in self.periods:
            next_time = self._find_next_period_time(current_time, period)
            for _ in range(count):
                times.append(next_time)
                next_time = self._advance_period(next_time, period)

        times.sort()
        return times[:count]

    def _find_next_period_time(self, current: datetime, period: TimePeriod) -> datetime:
        candidate = current.replace(hour=period.start_hour, minute=0, second=0, microsecond=0)
        if candidate <= current:
            candidate = self._advance_period(candidate, period)
        return candidate

    def _advance_period(self, t: datetime, period: TimePeriod) -> datetime:
        from datetime import timedelta
        return t + timedelta(hours=12)

    def should_crawl(self, current_time: Optional[datetime] = None) -> bool:
        return self.is_active(current_time) and self.actions.get("crawl", False)

    def should_analyze(self, current_time: Optional[datetime] = None) -> bool:
        return self.is_active(current_time) and self.actions.get("analyze", False)

    def should_push(self, current_time: Optional[datetime] = None) -> bool:
        return self.is_active(current_time) and self.actions.get("push", False)

    def get_active_period_name(self, current_time: Optional[datetime] = None) -> str:
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        current_hour = current_time.hour
        current_day = current_time.weekday()

        for period in self.periods:
            if current_day in period.days_of_week:
                if period.start_hour <= current_hour < period.end_hour:
                    return period.name
                if period.start_hour > period.end_hour:
                    if current_hour >= period.start_hour or current_hour < period.end_hour:
                        return period.name

        return "inactive"


def create_scheduler(config: dict) -> Scheduler:
    return Scheduler(config)