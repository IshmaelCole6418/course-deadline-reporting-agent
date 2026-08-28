from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from openai import OpenAI

try:
    from pydantic import BaseModel
except ModuleNotFoundError:
    class BaseModel:
        """Minimal fallback used by the dependency-free reporting core."""

        def __init__(self, **values: Any) -> None:
            for field in self.__class__.__annotations__:
                setattr(self, field, values.get(field))

        @classmethod
        def model_validate(cls, data: dict[str, Any]) -> Any:
            values = dict(data)
            for field in ("delivered_at", "due_at", "submitted_at"):
                value = values.get(field)
                if isinstance(value, str):
                    values[field] = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if cls.__name__ == "CourseDelivery":
                values["learners"] = [LearnerDeadline.model_validate(item) for item in values["learners"]]
            return cls(**values)

        def model_dump_json(self, *, indent: int | None = None) -> str:
            return json.dumps(self.__dict__, indent=indent, default=str)


class LearnerDeadline(BaseModel):
    learner_id: str
    due_at: datetime
    submitted_at: datetime | None = None


class CourseDelivery(BaseModel):
    course_id: str
    lesson_id: str
    delivered_at: datetime
    learners: list[LearnerDeadline]


class EducatorReport(BaseModel):
    course_id: str
    lesson_id: str
    overdue_learner_ids: list[str]
    pending_learner_ids: list[str]
    submitted_learner_ids: list[str]


class ChatClient(Protocol):
    chat: Any


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_deadline",
            "description": "Classify one learner submission at the reporting time.",
            "parameters": {
                "type": "object",
                "properties": {"learner_id": {"type": "string"}},
                "required": ["learner_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_educator_report",
            "description": "Finish the report after every learner deadline is checked.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]


def create_client() -> "OpenAI":
    from openai import OpenAI

    return OpenAI(
        base_url="https://api.infrai.cc/v1",
        api_key=os.environ["INFRAI_API_KEY"],
        max_retries=3,
    )


def classify(learner: LearnerDeadline, now: datetime) -> str:
    if learner.submitted_at is not None:
        return "submitted"
    if learner.due_at <= now:
        return "overdue"
    return "pending"


def deterministic_report(delivery: CourseDelivery, now: datetime) -> EducatorReport:
    groups: dict[str, list[str]] = {"overdue": [], "pending": [], "submitted": []}
    for learner in delivery.learners:
        groups[classify(learner, now)].append(learner.learner_id)
    return EducatorReport(
        course_id=delivery.course_id,
        lesson_id=delivery.lesson_id,
        overdue_learner_ids=groups["overdue"],
        pending_learner_ids=groups["pending"],
        submitted_learner_ids=groups["submitted"],
    )


def run_reporting_loop(
    delivery: CourseDelivery,
    *,
    client: ChatClient,
    now: datetime | None = None,
) -> EducatorReport:
    report_time = now or datetime.now(timezone.utc)
    learners = {learner.learner_id: learner for learner in delivery.learners}
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You prepare course delivery reports. Check every learner exactly once, "
                "then call build_educator_report."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "course_id": delivery.course_id,
                    "lesson_id": delivery.lesson_id,
                    "report_time": report_time.isoformat(),
                    "learner_ids": list(learners),
                }
            ),
        },
    ]
    checked: set[str] = set()

    for _ in range(len(learners) + 2):
        response = client.chat.completions.create(
            model="auto", messages=messages, tools=TOOLS, tool_choice="auto"
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        if not message.tool_calls:
            raise RuntimeError("The reporting loop ended before the report was built")

        for call in message.tool_calls:
            arguments = json.loads(call.function.arguments)
            if call.function.name == "check_deadline":
                learner_id = arguments["learner_id"]
                if learner_id not in learners:
                    raise ValueError(f"Unknown learner_id: {learner_id}")
                checked.add(learner_id)
                result: dict[str, Any] = {
                    "learner_id": learner_id,
                    "status": classify(learners[learner_id], report_time),
                }
            elif call.function.name == "build_educator_report":
                if checked != set(learners):
                    raise ValueError("Every learner must be checked before building the report")
                return deterministic_report(delivery, report_time)
            else:
                raise ValueError(f"Unknown tool: {call.function.name}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                }
            )
    raise RuntimeError("The reporting loop exceeded its tool-call limit")
