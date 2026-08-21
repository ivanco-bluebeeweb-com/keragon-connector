"""Imperal-side value-add functions -- capabilities that do not exist
1:1 in Keragon itself, built by combining this app's own stored state
(see CONNECTOR_DISCOVERY.md Tier 3).
"""
from __future__ import annotations

from imperal_sdk import ActionResult

from app import chat
from handlers_outgoing import _load_bridges
from handlers_inbound import get_inbound_status_data, _INBOUND_EVENTS_COLLECTION
from schemas import NoParams, BridgeHealthReport


@chat.function(
    "audit_bridge_health",
    "Aggregate health report across every configured Keragon bridge: how "
    "many outgoing bridges exist, whether the inbound webhook is ready, "
    "how many inbound events arrived per event_kind, and which bridges "
    "have never produced a matching inbound callback (a signal a "
    "workflow's trigger URL may be broken or misconfigured). Keragon "
    "itself has no cross-bridge delivery-history view -- this is built "
    "entirely from what Imperal has recorded on its own side.",
    action_type="read",
    chain_callable=True,
    data_model=BridgeHealthReport,
)
async def audit_bridge_health(ctx, params: NoParams) -> "ActionResult":
    """Aggregate health report across every configured Keragon bridge."""
    bridges = await _load_bridges(ctx)
    inbound_status = await get_inbound_status_data(ctx)

    page = await ctx.store.query(
        _INBOUND_EVENTS_COLLECTION, order_by="-received_at", limit=1000,
    )
    items = getattr(page, "data", None) or []
    event_kinds: dict[str, int] = {}
    seen_bridge_ids: set[str] = set()
    for doc in items:
        d = doc.data if hasattr(doc, "data") else doc
        d = d or {}
        kind = d.get("event_kind") or "(untagged)"
        event_kinds[kind] = event_kinds.get(kind, 0) + 1
        bid = d.get("bridge_id")
        if bid:
            seen_bridge_ids.add(bid)

    silent = [b.get("name", b.get("id", "")) for b in bridges if b.get("id") not in seen_bridge_ids]

    return ActionResult.success(
        BridgeHealthReport(
            outgoing_bridge_count=len(bridges),
            inbound_configured=inbound_status.configured,
            inbound_event_count_total=len(items),
            inbound_event_kinds=event_kinds,
            silent_bridges=silent,
            detail=(
                "All bridges have produced at least one tagged inbound callback."
                if bridges and not silent else
                "No outgoing bridges configured yet." if not bridges else
                f"{len(silent)} bridge(s) have never produced a matching inbound callback -- "
                "this is only a signal if you expect round-trip callbacks from that workflow, "
                "not every workflow needs one."
            ),
        ),
        summary=f"{len(bridges)} bridge(s), {len(items)} inbound event(s) recorded.",
    )
