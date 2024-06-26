import datetime
from typing import Any

from events.bot_event import BotEvent
from events.types import EventType


class TimeoutEvent(BotEvent):

    def __init__(
        self,
        timestamp: datetime.datetime,
        guild_id: int,
        member_id: int,
        duration: int,
        id: int = None,
    ):
        super().__init__(timestamp, guild_id, EventType.TIMEOUT, id)
        self.member_id = member_id
        self.duration = duration

    def get_causing_user_id(self) -> int:
        return self.member_id

    def get_type_specific_args(self) -> list[Any]:
        return [self.duration]

    @staticmethod
    def from_db_row(row: dict[str, Any]) -> "TimeoutEvent":
        from datalayer.database import Database

        if row is None:
            return None

        return TimeoutEvent(
            timestamp=datetime.datetime.fromtimestamp(
                row[Database.EVENT_TIMESTAMP_COL]
            ),
            guild_id=row[Database.EVENT_GUILD_ID_COL],
            member_id=row[Database.TIMEOUT_EVENT_MEMBER_COL],
            duration=row[Database.TIMEOUT_EVENT_DURATION_COL],
            id=row[Database.EVENT_ID_COL],
        )
