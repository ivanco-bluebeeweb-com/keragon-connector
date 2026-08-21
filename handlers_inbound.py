"""Incoming direction: Keragon -> Imperal, via a workflow's "HTTP Client
action" step POSTing into our webhook receiver.

Same shared-secret verification shape as Zapier Webhook's
receive_zapier_webhook (Keragon's HTTP Client action has no signing of
its own to verify against -- confirmed 2026-08-21,
help.keragon.com/.../How-to-use-the-HTTP-Client-action-to-make-custom-API-requests
documents plain configurable headers, not HMAC), but extended with two
Keragon-specific concepts a healthcare workflow actually needs:

  - event_kind: an optional free-text tag (e.g. "appointment_reminder",
    "intake_submitted") the workflow author puts in a query param or the
    JSON body, so incoming events from many different Keragon workflows
    can be told apart and filtered later.
  - bridge_id: an optional correlation id tying an inbound event back to
    one of the outgoing bridges (list_outgoing_bridges), for round-trip
    workflows (Imperal triggers Keragon, Keragon calls back with a
    result).
"""
from __future__ import annotations

import hmac
import json
import secrets as _secrets_mod
import time

from imperal_sdk import ActionResult

from app import ext, chat
from schemas import (
    NoParams,
    InboundWebhookConfig, RegenerateInboundSecretParams,
    ListInboundEventsParams, InboundEventSummary, InboundEventList,
    GetInboundEventParams, InboundEventDetail,
)

_INBOUND_SECRET_NAME = "keragon_inbound_shared_secret"
_INBOUND_HEADER_NAME = "X-Keragon-Webhook-Secret"

_INBOUND_EVENTS_COLLECTION = "keragon_inbound_events"
#: Keep the rolling log bounded -- this is a bridge, not an audit system.
_INBOUND_EVENTS_MAX = 200

_INBOUND_WEBHOOK_PATH = "/inbound"


def _build_inbound_url(ctx) -> str:
    """Public URL the user pastes into a Keragon "HTTP Client action"
    step's request URL field. Built the same way as the platform's own
    OAuth callback URLs (per decorators-reference.md):
    https://panel.imperal.io/v1/ext/<app_id>/webhook<path>.
    """
    app_id = getattr(ext, "app_id", None) or getattr(ext, "name", "keragon-connector")
    return f"https://panel.imperal.io/v1/ext/{app_id}/webhook{_INBOUND_WEBHOOK_PATH}"


async def get_inbound_status_data(ctx) -> InboundWebhookConfig:
    """Plain-data helper for panels.py (no ActionResult wrapping)."""
    secret = await ctx.secrets.get(_INBOUND_SECRET_NAME)
    return InboundWebhookConfig(
        configured=bool(secret),
        webhook_url=_build_inbound_url(ctx),
        detail=(
            "Ready to receive events" if secret
            else "Generate a shared secret first (regenerate_inbound_secret)"
        ),
    )


@chat.function(
    "get_inbound_webhook_config",
    "Read the inbound webhook URL and whether a shared secret is set up "
    "for receiving events FROM a Keragon workflow (via its 'HTTP Client "
    "action' step). Never reveals the secret itself.",
    action_type="read",
    chain_callable=True,
    data_model=InboundWebhookConfig,
)
async def get_inbound_webhook_config(ctx, params: NoParams) -> "ActionResult":
    """Read-only status of the inbound (Keragon -> Imperal) webhook setup."""
    data = await get_inbound_status_data(ctx)
    return ActionResult.success(
        data,
        summary="Inbound webhook is ready to receive events." if data.configured else "Inbound webhook needs a shared secret first.",
    )


@chat.function(
    "regenerate_inbound_secret",
    "Generate a fresh shared secret for the inbound direction (Keragon -> "
    "Imperal), discarding any previous one. Paste the new value into a "
    "custom header named X-Keragon-Webhook-Secret on your workflow's "
    "'HTTP Client action' step.",
    action_type="write",
    chain_callable=True,
    data_model=InboundWebhookConfig,
    event="keragon-connector.regenerate_inbound_secret",
    effects=["keragon.inbound_secret.rotated"],
)
async def regenerate_inbound_secret(ctx, params: RegenerateInboundSecretParams) -> "ActionResult":
    """Rotate the inbound shared secret; the old one stops being accepted immediately."""
    new_secret = _secrets_mod.token_urlsafe(32)
    await ctx.secrets.set(_INBOUND_SECRET_NAME, new_secret)
    return ActionResult.success(
        InboundWebhookConfig(
            configured=True,
            webhook_url=_build_inbound_url(ctx),
            detail=new_secret,  # surfaced once, in the write response, so the user can copy it
        ),
        summary="New inbound shared secret generated -- copy it now, it won't be shown again.",
        refresh_panels=["keragon_center", "keragon_settings"],
    )


@chat.function(
    "list_inbound_events",
    "List the most recent events a Keragon workflow has POSTed into this "
    "app via the inbound webhook, newest first. Optionally filter by "
    "event_kind.",
    action_type="read",
    chain_callable=True,
    data_model=InboundEventList,
)
async def list_inbound_events(ctx, params: ListInboundEventsParams) -> "ActionResult":
    """List recent inbound events, optionally filtered by event_kind."""
    where = {"event_kind": params.event_kind} if params.event_kind else None
    page = await ctx.store.query(
        _INBOUND_EVENTS_COLLECTION, where=where, order_by="-received_at",
        limit=_INBOUND_EVENTS_MAX,
    )
    items = getattr(page, "data", None) or []
    events = []
    for doc in items:
        d = doc.data if hasattr(doc, "data") else doc
        d = d or {}
        events.append(InboundEventSummary(
            id=str(getattr(doc, "id", getattr(doc, "doc_id", ""))),
            received_at=d.get("received_at", ""),
            event_kind=d.get("event_kind", ""),
            bridge_id=d.get("bridge_id", ""),
            payload_preview=d.get("payload_preview", ""),
        ))
    return ActionResult.success(
        InboundEventList(events=events, total=len(events)),
        summary=f"{len(events)} recent inbound event(s)." if events else "No inbound events yet.",
    )


@chat.function(
    "get_inbound_event",
    "Get the full stored body and headers preview of one inbound event, by id from list_inbound_events.",
    action_type="read",
    chain_callable=True,
    data_model=InboundEventDetail,
)
async def get_inbound_event(ctx, params: GetInboundEventParams) -> "ActionResult":
    """Read one stored inbound event's full body and headers preview."""
    doc = await ctx.store.get(_INBOUND_EVENTS_COLLECTION, params.event_id)
    if not doc:
        return ActionResult.error(f"No inbound event found with id '{params.event_id}'.")
    d = doc.data if hasattr(doc, "data") else doc
    d = d or {}
    return ActionResult.success(
        InboundEventDetail(
            id=params.event_id,
            received_at=d.get("received_at", ""),
            event_kind=d.get("event_kind", ""),
            bridge_id=d.get("bridge_id", ""),
            headers_preview=d.get("headers_preview", ""),
            body=d.get("body", ""),
        ),
        summary="Inbound event detail loaded.",
    )


# ──────────────────────────────────────────────────────────────────────────
# Inbound webhook receiver -- runs with NO user in context
# (ctx.user.imperal_id == "__webhook__"), reachable by anyone who knows
# the URL. Verification is a plain shared-secret header comparison via
# hmac.compare_digest (constant-time, per Zapier Webhook's / Slack
# Connector's own inbound.py precedent) -- Keragon's HTTP Client action
# step has no HMAC signing of its own to verify against, so a shared
# secret in a custom header is the correct minimum here.
# ──────────────────────────────────────────────────────────────────────────

@ext.webhook(_INBOUND_WEBHOOK_PATH, method="POST")
async def receive_keragon_webhook(ctx, headers: dict, body: str, query_params: dict):
    expected_secret = await ctx.secrets.get(_INBOUND_SECRET_NAME)
    if not expected_secret:
        return {"error": "Inbound webhook not configured yet"}

    # Header lookup is case-insensitive per HTTP semantics.
    lowered = {k.lower(): v for k, v in (headers or {}).items()}
    got_secret = lowered.get(_INBOUND_HEADER_NAME.lower(), "")

    if not hmac.compare_digest(got_secret, expected_secret):
        return {"error": "Invalid or missing shared secret"}

    # event_kind / bridge_id may arrive as query params (simplest for a
    # Keragon "HTTP Client action" step to set) or inside the JSON body.
    event_kind = (query_params or {}).get("event_kind", "")
    bridge_id = (query_params or {}).get("bridge_id", "")
    body_preview = (body or "")[:2000]
    if not event_kind or not bridge_id:
        try:
            parsed = json.loads(body or "{}")
            if isinstance(parsed, dict):
                event_kind = event_kind or str(parsed.get("event_kind", ""))
                bridge_id = bridge_id or str(parsed.get("bridge_id", ""))
        except Exception:
            pass

    headers_preview = ", ".join(sorted((headers or {}).keys()))[:500]

    await ctx.store.create(
        _INBOUND_EVENTS_COLLECTION,
        {
            "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event_kind": event_kind,
            "bridge_id": bridge_id,
            "payload_preview": body_preview[:500],
            "headers_preview": headers_preview,
            "body": body_preview,
        },
    )

    # Prune past the cap so this collection cannot grow without bound.
    page = await ctx.store.query(
        _INBOUND_EVENTS_COLLECTION, order_by="-received_at", limit=2000,
    )
    items = getattr(page, "data", None) or []
    if len(items) > _INBOUND_EVENTS_MAX:
        for doc in items[_INBOUND_EVENTS_MAX:]:
            doc_id = getattr(doc, "id", None) or getattr(doc, "doc_id", None)
            if doc_id:
                await ctx.store.delete(_INBOUND_EVENTS_COLLECTION, doc_id)

    return {"ok": True}
