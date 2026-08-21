"""Extension declaration, secrets, lifecycle hooks.

WHY THIS APP IS CALLED "Keragon", BUT IS A WEBHOOK BRIDGE, NOT A FULL
CRUD-STYLE CONNECTOR (same architectural class as Zapier Webhook).

Per CONNECTOR_DISCOVERY.md: Keragon (a HIPAA-compliant healthcare iPaaS)
does NOT expose a general management REST API for listing/creating/
running a customer's own workflows. The only two surfaces it gives an
external caller are: (1) "HTTP Webhook Trigger" -- a unique URL per
workflow that starts it on POST, and (2) "HTTP Client action" -- a step
INSIDE a Keragon workflow that can call out to any external HTTP
endpoint. `docs.keragon.com` documents a THIRD, unrelated surface: their
own CLI/SDK for building a connector INSIDE Keragon's catalog (so
Keragon's 300+ built-in integrations grow by one) -- that requires their
review process and is a different, much larger, separate project, not
this app. Keragon MCP (keragon.com/mcp) is also unrelated: it is
Keragon's OWN MCP server letting AI agents reach systems connected
INSIDE Keragon, not a way for Imperal to manage Keragon workflows.

WHY MULTIPLE NAMED BRIDGES, NOT ONE ANONYMOUS URL LIKE Zapier Webhook.

A healthcare team realistically runs many Keragon workflows at once
(patient intake, appointment reminders, insurance verification, no-show
recovery, etc.) -- each with its own HTTP Webhook Trigger URL. Modelling
this as a single slot (like Zapier Webhook's one Catch Hook URL) would
force the user to juggle one bridge at a time. Instead, outgoing bridges
are a named, labelled list (same "one secret holding a JSON array"
precedent as PagerDuty Connector's pagerduty_connections /
MuleSoft Connector's multi-environment connections) so a user can fire
"New patient intake" and "Appointment reminder" independently, from chat
or the panel, by name.

WHY A SEPARATE SHARED SECRET FOR THE INBOUND DIRECTION.

Symmetrically, a Keragon workflow's "HTTP Client action" step can POST
back into Imperal (e.g. to log a completed automation, or hand off to
another Imperal app). This is one single inbound endpoint (fixed path,
like Zapier Webhook's), guarded by a rotatable shared secret compared
with `hmac.compare_digest` -- not per-workflow, because Keragon itself
does not sign its outbound HTTP Client requests, so the only symmetric
verification available is a shared secret the user configures on both
sides (in the HTTP Client action's own headers, and here).
"""
from __future__ import annotations

from imperal_sdk import ChatExtension, Extension

ext = Extension(
    "keragon-connector",
    version="0.1.0",
    display_name="Keragon",
    description=(
        "Two-way webhook bridge between Imperal and Keragon, the "
        "HIPAA-compliant healthcare automation platform. Fire any number "
        "of named Keragon workflows from Imperal by POSTing to their HTTP "
        "Webhook Trigger URLs, and receive callbacks a Keragon workflow's "
        "HTTP Client action step sends back into Imperal -- plus bulk "
        "fan-out, delivery history, and templated healthcare event "
        "payloads Imperal builds on top. Keragon exposes no general "
        "workflow-management API (see this app's own notes), so this is "
        "deliberately a webhook bridge, not a CRUD connector."
    ),
    icon="icon.svg",
    capabilities=[
        "keragon:read",
        "keragon:write",
    ],
    actions_explicit=True,
    system=False,
)

chat = ChatExtension(
    ext,
    tool_name="keragon",
    description=(
        "Keragon Connector -- manage named outgoing bridges to Keragon "
        "healthcare workflows (HTTP Webhook Triggers), fire them singly "
        "or in bulk, configure the inbound callback secret for Keragon's "
        "HTTP Client action to reach back into Imperal, and read delivery "
        "history for both directions."
    ),
)

ext.secret(
    "keragon_outgoing_bridges",
    (
        "Your configured outgoing bridges to Keragon workflows -- stored "
        "as a JSON array, one entry per bridge, each with its own HTTP "
        "Webhook Trigger URL. Managed through create_outgoing_bridge / "
        "update_outgoing_bridge / delete_outgoing_bridge -- you should "
        "not need to edit this directly."
    ),
    required=False,
    write_mode="both",
    max_bytes=65536,
    rotation_hint_days=180,
)(lambda: None)

ext.secret(
    "keragon_inbound_shared_secret",
    (
        "The shared secret Keragon's HTTP Client action must send back "
        "in a header to prove a callback is genuinely from your Keragon "
        "workflow. Managed through set_inbound_secret / "
        "regenerate_inbound_secret."
    ),
    required=False,
    write_mode="both",
    max_bytes=4096,
    rotation_hint_days=90,
)(lambda: None)


@ext.health_check
async def health_check(ctx) -> dict:
    """Fast configuration health; no third-party call -- just confirms at
    least one outgoing bridge or the inbound secret is configured, same
    shape as PagerDuty Connector's / Zapier Webhook's health_check."""
    import json as _json
    raw = await ctx.secrets.get("keragon_outgoing_bridges")
    try:
        count = len(_json.loads(raw)) if raw else 0
    except Exception:
        count = 0
    inbound = bool(await ctx.secrets.get("keragon_inbound_shared_secret"))
    if count or inbound:
        parts = []
        if count:
            parts.append(f"{count} outgoing bridge(s)")
        if inbound:
            parts.append("inbound secret configured")
        detail = ", ".join(parts) + "."
    else:
        detail = "Not configured yet -- run create_outgoing_bridge or set_inbound_secret."
    return {"healthy": True, "detail": detail}
