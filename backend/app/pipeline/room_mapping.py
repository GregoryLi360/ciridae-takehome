from pydantic import BaseModel

from ..llm import chat


class RoomGroup(BaseModel):
    jdr_room: str | None = None
    ins_room: str | None = None


class _RoomMapping(BaseModel):
    groups: list[RoomGroup]


ROOM_MAPPING_PROMPT = """\
You are comparing two construction repair proposals for the same property.
Match rooms from the JDR (contractor) proposal to rooms from the Insurance proposal.

Rules:
- Pair rooms that refer to the same physical space (e.g. "Bathroom" ↔ "Hall Bathroom", "Bedroom 1" ↔ "Bedroom").
- Each room appears in exactly one pair. A pair has one JDR room and one Insurance room.
- If a room has no match on the other side, include it alone with null for the missing side.
- Use exact room names as provided — do not rename them."""


def map_rooms(jdr_rooms: list[str], ins_rooms: list[str]) -> list[RoomGroup]:
    user_msg = f"JDR rooms: {jdr_rooms}\nInsurance rooms: {ins_rooms}"
    result = chat(ROOM_MAPPING_PROMPT, user_msg, _RoomMapping)
    return result.groups
