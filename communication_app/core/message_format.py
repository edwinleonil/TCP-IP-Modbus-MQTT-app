"""Consistent JSON message format for cross-protocol communication."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class CommMessage:
    source: str
    timestamp: str
    type: str
    value: float | str | int | bool | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> "CommMessage":
        return cls(**json.loads(data))

    @classmethod
    def create(cls, source: str, msg_type: str, value=None) -> "CommMessage":
        return cls(
            source=source,
            timestamp=datetime.now(timezone.utc).isoformat(),
            type=msg_type,
            value=value,
        )
