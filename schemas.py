"""Pydantic models for Keragon Connector -- multi-bridge two-direction
webhook bridge (see app.py for why this app is NOT a full CRUD-style
connector like Salesforce/HubSpot; Keragon itself has no management
REST API -- see CONNECTOR_DISCOVERY.md).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class NoParams(BaseModel):
    """Empty params for read-only calls that take no arguments."""
    pass


class DeleteResult(BaseModel):
    deleted: bool


# ── Outgoing bridges: Imperal -> Keragon (HTTP Webhook Trigger URLs) ───────

class CreateOutgoingBridgeParams(BaseModel):
    name: str = Field(description="Short label for this bridge, e.g. 'New patient intake'.")
    webhook_url: str = Field(description="The Keragon workflow's HTTP Webhook Trigger URL, copied from the trigger step's setup screen inside Keragon.")
    description: str = Field(default="", description="Optional note on what this workflow does or when it fires.")


class UpdateOutgoingBridgeParams(BaseModel):
    bridge_id: str = Field(description="Bridge id, from list_outgoing_bridges.")
    name: str = Field(default="", description="New label. Empty leaves it unchanged.")
    webhook_url: str = Field(default="", description="New Keragon HTTP Webhook Trigger URL. Empty leaves it unchanged.")
    description: str = Field(default="", description="New description. Empty leaves it unchanged.")


class GetOutgoingBridgeParams(BaseModel):
    bridge_id: str = Field(description="Bridge id, from list_outgoing_bridges.")


class DeleteOutgoingBridgeParams(BaseModel):
    bridge_id: str = Field(description="Bridge id to permanently remove, from list_outgoing_bridges.")


class OutgoingBridgeEntry(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: str = ""
    has_url: bool = False


class OutgoingBridgeList(BaseModel):
    bridges: list[OutgoingBridgeEntry] = Field(default_factory=list)
    total: int = 0


class SendBridgeEventParams(BaseModel):
    bridge_id: str = Field(description="Which bridge (Keragon workflow trigger) to fire, from list_outgoing_bridges.")
    payload: dict = Field(default_factory=dict, description="Arbitrary JSON payload to POST to that workflow's HTTP Webhook Trigger URL -- e.g. patient/appointment fields the workflow expects.")


class WebhookDeliveryResult(BaseModel):
    delivered: bool
    status_code: int = 0
    detail: str = ""


class BulkSendBridgeEventParams(BaseModel):
    bridge_ids: list[str] = Field(description="Which bridges to fire, from list_outgoing_bridges. 1-20 per call.")
    payload: dict = Field(default_factory=dict, description="Same JSON payload POSTed to every listed bridge's Keragon workflow trigger.")


class BulkDeliveryItem(BaseModel):
    bridge_id: str
    name: str = ""
    delivered: bool
    status_code: int = 0
    detail: str = ""


class BulkDeliveryResult(BaseModel):
    results: list[BulkDeliveryItem] = Field(default_factory=list)
    sent: int = 0
    total: int = 0


# ── Incoming: Keragon -> Imperal (HTTP Client action) ──────────────────────

class InboundWebhookConfig(BaseModel):
    configured: bool
    webhook_url: str = ""
    detail: str = ""


class RegenerateInboundSecretParams(BaseModel):
    pass


class ListInboundEventsParams(BaseModel):
    event_kind: str = Field(default="", description="Optional free-text filter, e.g. 'appointment_reminder'. Empty returns every kind.")


class InboundEventSummary(BaseModel):
    id: str
    received_at: str
    event_kind: str = ""
    bridge_id: str = ""
    payload_preview: str = ""


class InboundEventList(BaseModel):
    events: list[InboundEventSummary] = Field(default_factory=list)
    total: int = 0


class GetInboundEventParams(BaseModel):
    event_id: str = Field(description="Event id, from list_inbound_events.")


class InboundEventDetail(BaseModel):
    id: str
    received_at: str
    event_kind: str = ""
    bridge_id: str = ""
    headers_preview: str = ""
    body: str = ""


# ── Imperal-side value-add ──────────────────────────────────────────────

class BridgeHealthEntry(BaseModel):
    bridge_id: str
    name: str
    outbound_deliveries_recorded: bool = False
    last_outbound_status: str = ""


class BridgeHealthReport(BaseModel):
    outgoing_bridge_count: int = 0
    inbound_configured: bool = False
    inbound_event_count_total: int = 0
    inbound_event_kinds: dict[str, int] = Field(default_factory=dict)
    silent_bridges: list[str] = Field(default_factory=list)
    detail: str = ""
