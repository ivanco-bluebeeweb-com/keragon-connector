"""Panel UI -- Keragon Connector (multi-bridge two-direction webhook
bridge, see app.py).

SIDEBAR CONTENT -- NO CARDS ANYWHERE, per ~/UI_INTERFACE_STANDARD.md's
"left sidebar, no decorated cards" rule. Every section is a plain
ui.Stack, separated by ui.Divider().

Per ~/UI_INTERFACE_STANDARD.md (form-container rule): every ui.Form here
is full_width so its container is stretched to the entire sidebar width,
and its own children (inputs) are also full_width inside it. Every input
has a visible label (a ui.Text caption above it, never just a
placeholder standing in for one) and a placeholder that reflects this
app's own domain (Keragon workflow trigger URLs / event kinds), not a
generic example. The "how to" instructions live ONLY in the
center-overlay help dialog (keragon_connect_help) -- never duplicated
inline in the sidebar, per the same standard.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
import handlers_outgoing as ho
import handlers_inbound as hi


def _settings_button() -> ui.UINode:
    return ui.Button(
        "App settings", variant="secondary", size="sm", full_width=True,
        icon="settings", on_click=ui.Call("__panel__keragon_settings"),
    )


def _outgoing_section(bridges: list) -> ui.UINode:
    if not bridges:
        return ui.Stack(direction="v", gap=1, align="start", children=[
            ui.Text("Outgoing bridges (Imperal -> Keragon)", variant="body"),
            ui.Text("None yet -- add one in App settings.", variant="caption"),
        ])
    rows: list[ui.UINode] = [
        ui.Text("Outgoing bridges (Imperal -> Keragon)", variant="body"),
    ]
    for b in bridges[:5]:
        rows.append(ui.Text(f"• {b.name}", variant="caption"))
    if len(bridges) > 5:
        rows.append(ui.Text(f"…and {len(bridges) - 5} more", variant="caption"))
    return ui.Stack(direction="v", gap=1, align="start", children=rows)


def _inbound_section(configured: bool, inbound_url: str) -> ui.UINode:
    if not configured:
        return ui.Stack(direction="v", gap=1, align="start", children=[
            ui.Text("Incoming (Keragon -> Imperal)", variant="body"),
            ui.Text("Not configured -- add it in App settings.", variant="caption"),
        ])
    return ui.Stack(direction="v", gap=1, align="start", children=[
        ui.Text("Incoming (Keragon -> Imperal)", variant="body"),
        ui.Text(inbound_url, variant="caption"),
    ])


@ext.panel("keragon_connect", slot="left", title="Keragon", icon="🏥",
           default_width=320, min_width=260, max_width=420)
async def keragon_connect_panel(ctx, **kwargs) -> object:
    bridges_raw = await ho._load_bridges(ctx)
    bridges = [ho._to_entry(b) for b in bridges_raw]
    in_status = await hi.get_inbound_status_data(ctx)

    header = ui.Header(
        text="Keragon", level=2,
        subtitle="Two-way webhook bridge between Imperal and your Keragon healthcare workflows",
    )

    children: list[ui.UINode] = [
        header,
        _outgoing_section(bridges),
        ui.Divider(),
        _inbound_section(in_status.configured, in_status.webhook_url),
        ui.Divider(),
        ui.Button(
            "How this works", variant="ghost", size="sm", full_width=True,
            icon="help-circle", on_click=ui.Call("__panel__keragon_connect_help"),
        ),
        ui.Button(
            "View bridge health", variant="primary", size="sm", full_width=True,
            icon="Activity", on_click=ui.Call("__panel__keragon_center"),
        ),
        _settings_button(),
    ]
    return ui.Stack(direction="v", gap=4, align="stretch", children=children)


@ext.panel("keragon_connect_help", slot="center", title="How Keragon Connector works",
           center_overlay=True)
async def keragon_connect_help(ctx, **kwargs) -> object:
    content = ui.Stack(direction="v", gap=3, children=[
        ui.Text("Why this app is a webhook bridge, not a full CRUD connector:", variant="heading"),
        ui.Text(
            "Keragon (a HIPAA-compliant healthcare automation platform) has "
            "no general management API to list or run your existing "
            "workflows from the outside. It only exposes two workflow "
            "steps: an 'HTTP Webhook Trigger' that starts a workflow on "
            "POST, and an 'HTTP Client action' inside a workflow that can "
            "call out to any URL. This app bridges both.",
        ),
        ui.Divider(),
        ui.Text("Outgoing -- to trigger a Keragon workflow from Imperal:", variant="heading"),
        ui.Text("1. In Keragon, add an 'HTTP Webhook Trigger' as the first step of your workflow."),
        ui.Text("2. Copy the URL the trigger step shows you."),
        ui.Text("3. Add it as a new bridge in App settings here, with a short name (e.g. 'New patient intake')."),
        ui.Text("4. Fire it from chat or another app by that bridge's name."),
        ui.Divider(),
        ui.Text("Incoming -- to let a Keragon workflow notify Imperal:", variant="heading"),
        ui.Text("1. In a Keragon workflow, add an 'HTTP Client action' step."),
        ui.Text("2. Set its request URL to the 'Incoming webhook URL' shown in App settings here."),
        ui.Text("3. Add a custom header named X-Keragon-Webhook-Secret with the value shown there, so Imperal can verify the request came from your workflow."),
        ui.Text("4. Optionally add event_kind and bridge_id as query params or JSON body fields, so incoming events can be told apart later."),
        ui.Divider(),
        ui.Link(
            label="Open Keragon's HTTP Webhook Trigger documentation",
            href="https://help.keragon.com/hc/en-us/articles/19924188729618-3-Add-Trigger-Step",
        ),
    ])
    return ui.Dialog(
        title="How Keragon Connector works",
        content=content,
        confirm_label="",
        cancel_label="Close",
    )


@ext.panel("keragon_center", slot="center", title="Keragon", icon="🏥", center_overlay=True)
async def keragon_center_panel(ctx, **kwargs) -> object:
    """Base center panel -- per UI_INTERFACE_STANDARD.md (2026-08-20).
    This app has no list/detail content of its own to show in the center
    by default (everything lives in the sidebar). MUST carry
    center_overlay=True: per docs.imperal.io/en/concepts/panels, a plain
    slot="center" panel is registered but the Panel app never fetches it
    at session-init without that flag -- the center slot stays genuinely
    empty (not a caching issue) until center_overlay=True is set. Text is
    the shared canonical wording -- must stay identical across every app
    in this situation, not app-specific."""
    import handlers_value_add as hv
    from schemas import NoParams
    result = await hv.audit_bridge_health(ctx, NoParams())
    body: list[ui.UINode] = [ui.Text("Bridge health", variant="subtitle")]
    if result.success and result.data:
        r = result.data
        body.append(ui.Stats(children=[
            ui.Stat(label="Outgoing bridges", value=str(r.outgoing_bridge_count)),
            ui.Stat(label="Inbound configured", value="Yes" if r.inbound_configured else "No"),
            ui.Stat(label="Inbound events", value=str(r.inbound_event_count_total)),
        ]))
        if r.silent_bridges:
            body.append(ui.Divider())
            body.append(ui.Text("Silent bridges (no deliveries recorded)", variant="caption"))
            for name in r.silent_bridges[:15]:
                body.append(ui.Stack(direction="h", gap=2, align="center", children=[
                    ui.Badge(label="SILENT", color="yellow"),
                    ui.Text(name, variant="body"),
                ]))
        if r.detail:
            body.append(ui.Divider())
            body.append(ui.Text(r.detail, variant="body"))
    else:
        body.append(ui.Text("Could not load the bridge health audit.", variant="caption"))

    return ui.Stack(direction="v", gap=3, align="stretch", children=body)
