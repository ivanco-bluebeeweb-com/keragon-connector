"""Outgoing bridges: Imperal -> Keragon (HTTP Webhook Trigger URLs).

Named, multi-bridge design -- unlike Zapier Webhook's single anonymous
URL -- because a healthcare team realistically runs many Keragon
workflows at once. Bridges are stored as a JSON array in one secret
(keragon_outgoing_bridges), same "one secret, one JSON array" precedent
as PagerDuty Connector's pagerduty_connections / MuleSoft Connector's
multi-environment connections (see app.py for the full reasoning).
"""
from __future__ import annotations

import json
import secrets as _secrets_mod
import time

from imperal_sdk import ActionResult

import keragon_client as kc
from app import chat
from schemas import (
    NoParams,
    CreateOutgoingBridgeParams, UpdateOutgoingBridgeParams,
    GetOutgoingBridgeParams, DeleteOutgoingBridgeParams,
    OutgoingBridgeEntry, OutgoingBridgeList,
    SendBridgeEventParams, WebhookDeliveryResult,
    BulkSendBridgeEventParams, BulkDeliveryResult, BulkDeliveryItem,
    DeleteResult,
)

_BRIDGES_SECRET = "keragon_outgoing_bridges"


# ── internal helpers ────────────────────────────────────────────────────

async def _load_bridges(ctx) -> list[dict]:
    raw = await ctx.secrets.get(_BRIDGES_SECRET)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


async def _save_bridges(ctx, bridges: list[dict]) -> None:
    await ctx.secrets.set(_BRIDGES_SECRET, json.dumps(bridges))


def _to_entry(b: dict) -> OutgoingBridgeEntry:
    return OutgoingBridgeEntry(
        id=b.get("id", ""), name=b.get("name", ""),
        description=b.get("description", ""),
        created_at=b.get("created_at", ""),
        has_url=bool(b.get("webhook_url")),
    )


def _find(bridges: list[dict], bridge_id: str) -> dict | None:
    for b in bridges:
        if b.get("id") == bridge_id:
            return b
    return None


# ── CRUD ────────────────────────────────────────────────────────────────

@chat.function(
    "create_outgoing_bridge",
    "Register a new named bridge to a Keragon workflow -- paste the "
    "workflow's HTTP Webhook Trigger URL (from the trigger step's setup "
    "screen inside Keragon) and give it a short label so you can fire it "
    "by name later with send_bridge_event.",
    action_type="write",
    chain_callable=True,
    data_model=OutgoingBridgeEntry,
    event="keragon-connector.create_outgoing_bridge",
    effects=["keragon.outgoing_bridge.created"],
)
async def create_outgoing_bridge(ctx, params: CreateOutgoingBridgeParams) -> "ActionResult":
    """Register a new named outgoing bridge to a Keragon workflow."""
    url = params.webhook_url.strip()
    if not (url.startswith("https://") or url.startswith("http://")):
        return ActionResult.error(
            "That doesn't look like a URL. Paste the HTTP Webhook Trigger "
            "URL from the trigger step's setup screen inside your Keragon "
            "workflow."
        )
    if not params.name.strip():
        return ActionResult.error("Please give this bridge a short name.")
    bridges = await _load_bridges(ctx)
    entry = {
        "id": _secrets_mod.token_hex(6),
        "name": params.name.strip(),
        "description": params.description.strip(),
        "webhook_url": url,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    bridges.append(entry)
    await _save_bridges(ctx, bridges)
    return ActionResult.success(
        _to_entry(entry),
        summary=f"Bridge '{entry['name']}' created.",
        refresh_panels=["keragon_center", "keragon_settings"],
    )


@chat.function(
    "list_outgoing_bridges",
    "List your configured outgoing bridges to Keragon workflows -- names "
    "and descriptions only, never the underlying trigger URLs.",
    action_type="read",
    chain_callable=True,
    data_model=OutgoingBridgeList,
)
async def list_outgoing_bridges(ctx, params: NoParams) -> "ActionResult":
    """List configured outgoing bridges."""
    bridges = await _load_bridges(ctx)
    items = [_to_entry(b) for b in bridges]
    return ActionResult.success(
        OutgoingBridgeList(bridges=items, total=len(items)),
        summary=f"{len(items)} outgoing bridge(s)." if items else "No outgoing bridges configured yet.",
    )


@chat.function(
    "get_outgoing_bridge",
    "Read one outgoing bridge's name and description by id (never the "
    "underlying trigger URL).",
    action_type="read",
    chain_callable=True,
    data_model=OutgoingBridgeEntry,
)
async def get_outgoing_bridge(ctx, params: GetOutgoingBridgeParams) -> "ActionResult":
    """Read one outgoing bridge by id."""
    bridges = await _load_bridges(ctx)
    b = _find(bridges, params.bridge_id)
    if not b:
        return ActionResult.error("No bridge found with that id. Check list_outgoing_bridges.")
    return ActionResult.success(_to_entry(b), summary=f"Bridge '{b.get('name', '')}'.")


@chat.function(
    "update_outgoing_bridge",
    "Update an existing outgoing bridge's name, trigger URL, and/or "
    "description. Only given fields change.",
    action_type="write",
    chain_callable=True,
    data_model=OutgoingBridgeEntry,
    event="keragon-connector.update_outgoing_bridge",
    effects=["keragon.outgoing_bridge.updated"],
)
async def update_outgoing_bridge(ctx, params: UpdateOutgoingBridgeParams) -> "ActionResult":
    """Update an existing outgoing bridge's name, URL, and/or description."""
    bridges = await _load_bridges(ctx)
    b = _find(bridges, params.bridge_id)
    if not b:
        return ActionResult.error("No bridge found with that id. Check list_outgoing_bridges.")
    if params.name.strip():
        b["name"] = params.name.strip()
    if params.webhook_url.strip():
        url = params.webhook_url.strip()
        if not (url.startswith("https://") or url.startswith("http://")):
            return ActionResult.error("That doesn't look like a URL for the new trigger URL.")
        b["webhook_url"] = url
    if params.description.strip():
        b["description"] = params.description.strip()
    await _save_bridges(ctx, bridges)
    return ActionResult.success(
        _to_entry(b),
        summary=f"Bridge '{b.get('name', '')}' updated.",
        refresh_panels=["keragon_center", "keragon_settings"],
    )


@chat.function(
    "delete_outgoing_bridge",
    "Permanently remove an outgoing bridge. Cannot be undone -- the "
    "Keragon workflow itself is unaffected, only Imperal forgets its URL.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="keragon-connector.delete_outgoing_bridge",
    effects=["keragon.outgoing_bridge.deleted"],
)
async def delete_outgoing_bridge(ctx, params: DeleteOutgoingBridgeParams) -> "ActionResult":
    """Permanently delete an outgoing bridge."""
    bridges = await _load_bridges(ctx)
    b = _find(bridges, params.bridge_id)
    if not b:
        return ActionResult.error("No bridge found with that id. Check list_outgoing_bridges.")
    bridges = [x for x in bridges if x.get("id") != params.bridge_id]
    await _save_bridges(ctx, bridges)
    return ActionResult.success(
        DeleteResult(deleted=True),
        summary=f"Bridge '{b.get('name', '')}' deleted.",
        refresh_panels=["keragon_center", "keragon_settings"],
    )


# ── firing ──────────────────────────────────────────────────────────────

@chat.function(
    "send_bridge_event",
    "Fire one configured Keragon workflow right now by POSTing a JSON "
    "payload to its HTTP Webhook Trigger URL. Run create_outgoing_bridge "
    "first if you haven't registered this workflow yet.",
    action_type="write",
    chain_callable=True,
    data_model=WebhookDeliveryResult,
    event="keragon-connector.send_bridge_event",
    effects=["keragon.bridge.sent"],
)
async def send_bridge_event(ctx, params: SendBridgeEventParams) -> "ActionResult":
    """Fire one configured Keragon workflow by POSTing a payload to its trigger URL."""
    bridges = await _load_bridges(ctx)
    b = _find(bridges, params.bridge_id)
    if not b:
        return ActionResult.error("No bridge found with that id. Check list_outgoing_bridges.")
    delivered, status_code, detail = await kc.post_webhook(ctx, b["webhook_url"], params.payload)
    result = WebhookDeliveryResult(delivered=delivered, status_code=status_code, detail=detail)
    if delivered:
        return ActionResult.success(result, summary=f"'{b.get('name', '')}' triggered (HTTP {status_code}).")
    return ActionResult.error(f"Delivery to '{b.get('name', '')}' failed: {detail}")


@chat.function(
    "bulk_send_bridge_event",
    "Fire the SAME payload to several configured Keragon workflows in one "
    "call -- e.g. notify both 'New patient intake' and 'Slack alert' "
    "bridges at once. Continues past per-bridge failures and reports "
    "each outcome. This is an Imperal-side convenience -- Keragon itself "
    "has no bulk-trigger endpoint.",
    action_type="write",
    chain_callable=True,
    data_model=BulkDeliveryResult,
    event="keragon-connector.bulk_send_bridge_event",
    effects=["keragon.bridge.sent"],
)
async def bulk_send_bridge_event(ctx, params: BulkSendBridgeEventParams) -> "ActionResult":
    """Fire the same payload to several configured Keragon workflows in one call."""
    bridges = await _load_bridges(ctx)
    results: list[BulkDeliveryItem] = []
    sent = 0
    for bridge_id in params.bridge_ids:
        b = _find(bridges, bridge_id)
        if not b:
            results.append(BulkDeliveryItem(
                bridge_id=bridge_id, name="", delivered=False, status_code=0,
                detail="No bridge found with that id.",
            ))
            continue
        delivered, status_code, detail = await kc.post_webhook(ctx, b["webhook_url"], params.payload)
        if delivered:
            sent += 1
        results.append(BulkDeliveryItem(
            bridge_id=bridge_id, name=b.get("name", ""), delivered=delivered,
            status_code=status_code, detail=detail,
        ))
    return ActionResult.success(
        BulkDeliveryResult(results=results, sent=sent, total=len(results)),
        summary=f"{sent}/{len(results)} bridge(s) triggered successfully.",
    )
