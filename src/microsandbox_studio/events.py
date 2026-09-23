"""Events for the frontend: batching and the JavaScript that delivers them."""

import base64
import json
from typing import Any

type Event = tuple[str, dict[str, Any]]


def js_call(event: str, payload: dict[str, Any]) -> str:
    return f"window.msbEvent({json.dumps(event)}, {json.dumps(payload)})"


def enqueue(outbox: list[Event], event: str, payload: dict[str, Any]) -> list[Event]:
    """``outbox`` with the event added; output for the same terminal joins the last entry."""
    if outbox and event == "terminal-data":
        last_event, last = outbox[-1]
        if last_event == event and last["token"] == payload["token"]:
            return [*outbox[:-1], (event, {**last, "data": last["data"] + payload["data"]})]
    return [*outbox, (event, payload)]


def _encoded(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    if event != "terminal-data":
        return payload
    return {**payload, "data": base64.b64encode(payload["data"]).decode("ascii")}


def script(batch: list[Event]) -> str:
    """One script for a batch, so the GUI thread gets one evaluate_js per batch."""
    return ";".join(js_call(event, _encoded(event, payload)) for event, payload in batch)
