"""
Схема шаблона сезона (§5 ТЗ) — pydantic-модели для валидации YAML-файлов из
app/seasons_library/. Шаблоны версионируются в git и правит их тренер, а не
код — поэтому ломаный YAML должен падать на валидации, а не тихо проезжать
в прод.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class Metric(BaseModel):
    name: str
    unit: str
    direction: Literal["up", "down"]


class BaselineTest(BaseModel):
    prompt: str
    input: Literal["number"]
    min: float
    max: float

    @model_validator(mode="after")
    def _check_range(self) -> "BaselineTest":
        if self.min >= self.max:
            raise ValueError("baseline_test: min должен быть меньше max")
        return self


class Eligibility(BaseModel):
    min_age: int = 18
    warnings: list[str] = Field(default_factory=list)


class Schedule(BaseModel):
    train_days: list[int] = Field(min_length=1)
    minutes: list[int] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def _check(self) -> "Schedule":
        if any(d < 1 or d > 7 for d in self.train_days):
            raise ValueError("schedule.train_days: дни недели — числа 1..7 (пн..вс)")
        if len(set(self.train_days)) != len(self.train_days):
            raise ValueError("schedule.train_days: дни не должны повторяться")
        if self.minutes[0] > self.minutes[1]:
            raise ValueError("schedule.minutes: [мин, макс] — мин не может быть больше макс")
        return self


class SeasonDayTemplate(BaseModel):
    title: str
    instructions: str
    minimal: str
    # Ожидаемый прирост метрики за одну выполненную тренировку (в единицах
    # metric.unit) — используется в прогнозе (§6). Не доля 0..1: для
    # "минут бега" это может быть 0.4, для "подтягиваний" — 1-2.
    expected_progress: float = Field(gt=0)


class Phase(BaseModel):
    phase: int = Field(ge=1)
    unlock_if_baseline_gte: float
    days: list[SeasonDayTemplate] = Field(min_length=1)


class RestDay(BaseModel):
    title: str
    instructions: str


class Measure(BaseModel):
    prompt: str
    proof: Literal["optional", "photo", "screenshot"] = "optional"
    progress_photo: bool = False


class Safety(BaseModel):
    max_phase_jump: int = Field(default=1, ge=1)
    rest_days_min_per_week: int = Field(default=1, ge=0)


class SeasonTemplate(BaseModel):
    id: str
    version: int = Field(ge=1)
    title: str
    title_uz: Optional[str] = None
    category: str
    metric: Metric
    lengths: list[Literal[30, 60, 90]] = Field(min_length=1)
    target_default: float
    baseline_test: BaselineTest
    eligibility: Eligibility
    schedule: Schedule
    phases: list[Phase] = Field(min_length=1)
    rest_day: RestDay
    measure_every_days: int = Field(gt=0)
    measure: Measure
    safety: Safety

    @model_validator(mode="after")
    def _check_phases_sequential(self) -> "SeasonTemplate":
        numbers = [p.phase for p in self.phases]
        if numbers != sorted(numbers) or len(set(numbers)) != len(numbers):
            raise ValueError("phases: номера фаз должны быть уникальны и идти по возрастанию")
        if numbers[0] != 1:
            raise ValueError("phases: первая фаза должна иметь phase=1")
        baselines = [p.unlock_if_baseline_gte for p in self.phases]
        if baselines != sorted(baselines):
            raise ValueError("phases: unlock_if_baseline_gte должен расти вместе с phase")
        return self
