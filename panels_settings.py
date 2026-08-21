"""The single 'App settings' screen (center slot) -- everything
configurable for Keragon Connector: outgoing bridges (Imperal ->
Keragon workflows) and the inbound shared secret (Keragon -> Imperal),
plus the recent inbound events log. Split out of panels.py per the same
convention as Zapier Webhook's / Make.com Connector's panels_settings.py.

Per ~/UI_INTERFACE_STANDARD.md: every ui.Form here is full_width so its
container stretches to the entire sidebar/dialog width, and its own
input children are also full_width. Every input carries a real label (a
ui.Text caption above it) in addition to a placeholder written for this
app's own domain -- never a bare placeholder standing in for a label,
never a generic example. "How to" instructions live only in the
center-overlay help dialog (keragon_connect_help), not duplicated here.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
import handlers_outgoing as ho
import handlers_inbound as hi


def _outgoing_section(bridges: list) -> ui.UINode:
    """Named outgoing bridges -- other Imperal apps / chat fire a Keragon
    workflow via send_bridge_event against one of these, by name."""
    rows: list[ui.UINode] = [
        ui.Text("Outgoing bridges (Imperal -> Keragon)", variant="heading"),
        ui.Text(
            "Each bridge fires one Keragon workflow's HTTP Webhook Trigger.",
            variant="caption",
        ),
    ]
    if bridges:
        items = [
            ui.ListItem(
                id=b.id, title=b.name,
                subtitle=b.description or "No description",
                trailing=ui.Button(
                    "Delete", variant="ghost", size="sm", icon="trash-2",
                    on_click=ui.Call("delete_outgoing_bridge", bridge_id=b.id),
                ),
            )
            for b in bridges
        ]
        rows.append(ui.List(items=items))
    else:
        rows.append(ui.Text("No bridges configured yet.", variant="caption"))

    rows.append(ui.Form(
        full_width=True,
        children=[
            ui.Stack(direction="v", gap=1, align="stretch", full_width=True, children=[
                ui.Text("Bridge name", variant="caption"),
                ui.Input(
                    placeholder="New patient intake",
                    param_name="name",
                    full_width=True,
                ),
            ]),
            ui.Stack(direction="v", gap=1, align="stretch", full_width=True, children=[
                ui.Text("Keragon HTTP Webhook Trigger URL", variant="caption"),
                ui.Input(
                    placeholder="https://hook.keragon.com/trigger/...",
                    param_name="webhook_url",
                    full_width=True,
                ),
            ]),
            ui.Stack(direction="v", gap=1, align="stretch", full_width=True, children=[
                ui.Text("Description (optional)", variant="caption"),
                ui.Input(
                    placeholder="Fires when a new patient submits the intake form",
                    param_name="description",
                    full_width=True,
                ),
            ]),
        ],
        submit_label="Add bridge",
        action="create_outgoing_bridge",
    ))
    return ui.Stack(direction="v", gap=2, align="stretch", full_width=True, children=rows)


def _inbound_section(configured: bool, webhook_url: str) -> ui.UINode:
    """Inbound direction -- a Keragon workflow's 'HTTP Client action' step
    hits this app's fixed URL with a shared secret in a custom header."""
    rows: list[ui.UINode] = [
        ui.Text("Incoming webhook (Keragon -> Imperal)", variant="heading"),
        ui.Text("Request URL", variant="caption"),
        ui.Text(webhook_url, variant="body"),
        ui.Text("Header name to add in your workflow's HTTP Client action step", variant="caption"),
        ui.Text("X-Keragon-Webhook-Secret", variant="body"),
    ]
    if configured:
        rows.append(ui.Badge(label="Ready to receive events", color="green"))
        rows.append(ui.Text(
            "Regenerating replaces the secret immediately -- update the "
            "header value in your workflow's action step right after.",
            variant="caption",
        ))
        rows.append(ui.Button(
            "Regenerate secret", variant="secondary", size="sm", full_width=True,
            icon="refresh-cw",
            on_click=ui.Call("regenerate_inbound_secret"),
        ))
    else:
        rows.append(ui.Text(
            "No shared secret yet -- generate one, then paste it as the "
            "header's value in your workflow's action step.",
            variant="caption",
        ))
        rows.append(ui.Button(
            "Generate shared secret", variant="primary", size="sm", full_width=True,
            icon="key", on_click=ui.Call("regenerate_inbound_secret"),
        ))
    return ui.Stack(direction="v", gap=2, align="stretch", full_width=True, children=rows)


def _recent_events_section(events: list) -> ui.UINode:
    if not events:
        return ui.Stack(direction="v", gap=2, children=[
            ui.Text("Recent inbound events", variant="heading"),
            ui.Text("No events received yet.", variant="caption"),
        ])
    items = [
        ui.ListItem(
            id=e.id,
            title=e.received_at,
            subtitle=f"{e.event_kind or '(untagged)'} -- {e.payload_preview[:100]}",
        )
        for e in events
    ]
    return ui.Stack(direction="v", gap=2, children=[
        ui.Text("Recent inbound events", variant="heading"),
        ui.List(items=items),
    ])


@ext.panel("keragon_settings", slot="center", title="App settings", icon="⚙️",
           center_overlay=True)
async def keragon_settings_panel(ctx, **kwargs) -> object:
    bridges_raw = await ho._load_bridges(ctx)
    bridges = [ho._to_entry(b) for b in bridges_raw]
    in_status = await hi.get_inbound_status_data(ctx)

    events = []
    try:
        page = await ctx.store.query(
            hi._INBOUND_EVENTS_COLLECTION, order_by="-received_at", limit=10,
        )
        items = getattr(page, "data", None) or []
        for doc in items:
            data = doc.data if hasattr(doc, "data") else doc
            data = data or {}
            events.append(type("E", (), {
                "id": str(getattr(doc, "id", getattr(doc, "doc_id", ""))),
                "received_at": data.get("received_at", ""),
                "event_kind": data.get("event_kind", ""),
                "payload_preview": data.get("payload_preview", ""),
            })())
    except Exception:
        events = []

    content = ui.Stack(direction="v", gap=4, align="stretch", full_width=True, children=[
        _outgoing_section(bridges),
        ui.Divider(),
        _inbound_section(in_status.configured, in_status.webhook_url),
        ui.Divider(),
        _recent_events_section(events),
    ])
    return ui.Dialog(
        title="App settings",
        content=content,
        confirm_label="",
        cancel_label="Close",
    )
