"""Plausible Scenario Testing (PST) for Keragon Connector.

Method: Docs/session-notes/SCENARIO_TESTING_STANDARD.md. Persona used
throughout: the Keragon account owner -- the one person who configures
both directions of this bridge: registers named outgoing bridges (one
per Keragon workflow's HTTP Webhook Trigger URL) to fire workflows FROM
Imperal, and generates a shared secret so a workflow's own "HTTP Client
action" step can send events IN. Single functional role; scenario
variety comes from DATA classes (empty/typical/boundary/invalid/exotic
states) and the 5 required branches.

Every test calls the REAL handler chat functions (and the REAL
@ext.webhook receiver) with REAL params models, through
imperal_sdk.testing.MockContext -- not a re-implementation of the logic
under a different name.
"""
from __future__ import annotations

import pytest

import handlers_outgoing as ho
import handlers_inbound as hi
import handlers_value_add as hv
from schemas import (
    NoParams,
    CreateOutgoingBridgeParams,
    UpdateOutgoingBridgeParams,
    GetOutgoingBridgeParams,
    DeleteOutgoingBridgeParams,
    SendBridgeEventParams,
    BulkSendBridgeEventParams,
    RegenerateInboundSecretParams,
    ListInboundEventsParams,
    GetInboundEventParams,
)


# ──────────────────────────────────────────────────────────────────────────
# Branch 1 -- Empty state (nothing configured yet)
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_outgoing_bridges_empty(ctx):
    result = await ho.list_outgoing_bridges(ctx, NoParams())
    assert result.status == "success"
    assert result.data.bridges == []
    assert result.data.total == 0


@pytest.mark.asyncio
async def test_send_bridge_event_with_no_bridges_errors_cleanly(ctx):
    result = await ho.send_bridge_event(ctx, SendBridgeEventParams(bridge_id="nope", payload={"a": 1}))
    assert result.status == "error"
    assert "No bridge found" in result.error


@pytest.mark.asyncio
async def test_inbound_config_empty_reports_not_configured(ctx):
    result = await hi.get_inbound_webhook_config(ctx, NoParams())
    assert result.status == "success"
    assert result.data.configured is False
    assert result.data.webhook_url  # URL is always derivable, even unconfigured


@pytest.mark.asyncio
async def test_list_inbound_events_empty_returns_empty_list(ctx):
    result = await hi.list_inbound_events(ctx, ListInboundEventsParams(event_kind=""))
    assert result.status == "success"
    assert result.data.events == []
    assert result.data.total == 0


@pytest.mark.asyncio
async def test_audit_bridge_health_empty_state(ctx):
    result = await hv.audit_bridge_health(ctx, NoParams())
    assert result.status == "success"
    assert result.data.outgoing_bridge_count == 0
    assert result.data.inbound_configured is False


# ──────────────────────────────────────────────────────────────────────────
# Branch 2 -- Typical state (the everyday, happy path)
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_then_list_outgoing_bridge(ctx):
    created = await ho.create_outgoing_bridge(
        ctx, CreateOutgoingBridgeParams(
            name="New patient intake", webhook_url="https://hooks.keragon.com/trigger/abc123",
            description="Fires on new intake form",
        ),
    )
    assert created.status == "success"
    assert created.data.name == "New patient intake"

    listed = await ho.list_outgoing_bridges(ctx, NoParams())
    assert listed.data.total == 1
    assert listed.data.bridges[0].has_url is True


@pytest.mark.asyncio
async def test_send_bridge_event_delivers_through_real_http_call(ctx_with_bridge):
    ctx_with_bridge.http.mock_post("hooks.keragon.com", response={}, status=200)
    result = await ho.send_bridge_event(
        ctx_with_bridge, SendBridgeEventParams(bridge_id="br_test1", payload={"patient_id": 42}),
    )
    assert result.status == "success"
    assert result.data.delivered is True
    assert result.data.status_code == 200


@pytest.mark.asyncio
async def test_regenerate_inbound_secret_then_config_reports_configured(ctx):
    result = await hi.regenerate_inbound_secret(ctx, RegenerateInboundSecretParams())
    assert result.status == "success"
    assert result.data.configured is True
    first_secret = result.data.detail
    assert first_secret  # surfaced once in the write response

    config = await hi.get_inbound_webhook_config(ctx, NoParams())
    assert config.data.configured is True


@pytest.mark.asyncio
async def test_receive_keragon_webhook_with_correct_secret_is_accepted(ctx_inbound_configured):
    result = await hi.receive_keragon_webhook(
        ctx_inbound_configured,
        headers={"X-Keragon-Webhook-Secret": "test-shared-secret-9f21ab"},
        body='{"event_kind": "appointment_reminder", "patient": "Jane"}',
        query_params={},
    )
    assert result.get("ok") is True

    events = await hi.list_inbound_events(ctx_inbound_configured, ListInboundEventsParams(event_kind=""))
    assert events.data.total == 1
    assert events.data.events[0].event_kind == "appointment_reminder"


@pytest.mark.asyncio
async def test_bulk_send_bridge_event_across_two_bridges(ctx):
    await ho.create_outgoing_bridge(ctx, CreateOutgoingBridgeParams(name="A", webhook_url="https://hooks.keragon.com/a"))
    await ho.create_outgoing_bridge(ctx, CreateOutgoingBridgeParams(name="B", webhook_url="https://hooks.keragon.com/b"))
    listed = await ho.list_outgoing_bridges(ctx, NoParams())
    ids = [b.id for b in listed.data.bridges]

    ctx.http.mock_post("hooks.keragon.com", response={}, status=200)
    result = await ho.bulk_send_bridge_event(ctx, BulkSendBridgeEventParams(bridge_ids=ids, payload={"x": 1}))
    assert result.status == "success"
    assert result.data.sent == 2
    assert result.data.total == 2


# ──────────────────────────────────────────────────────────────────────────
# Branch 3 -- Boundary state (case-insensitive header, empty body, cap)
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_receive_keragon_webhook_header_lookup_is_case_insensitive(ctx_inbound_configured):
    result = await hi.receive_keragon_webhook(
        ctx_inbound_configured,
        headers={"x-keragon-webhook-secret": "test-shared-secret-9f21ab"},
        body="{}",
        query_params={},
    )
    assert result.get("ok") is True


@pytest.mark.asyncio
async def test_receive_keragon_webhook_empty_body_is_still_accepted(ctx_inbound_configured):
    """An empty POST body is a plausible real event (some HTTP Client action
    steps send no body at all) -- it must not crash the receiver."""
    result = await hi.receive_keragon_webhook(
        ctx_inbound_configured,
        headers={"X-Keragon-Webhook-Secret": "test-shared-secret-9f21ab"},
        body="",
        query_params={},
    )
    assert result.get("ok") is True


@pytest.mark.asyncio
async def test_receive_keragon_webhook_event_kind_from_query_param(ctx_inbound_configured):
    """event_kind/bridge_id can arrive as query params -- simplest for a
    Keragon HTTP Client action step to set without touching the JSON body."""
    result = await hi.receive_keragon_webhook(
        ctx_inbound_configured,
        headers={"X-Keragon-Webhook-Secret": "test-shared-secret-9f21ab"},
        body="{}",
        query_params={"event_kind": "no_show", "bridge_id": "br_test1"},
    )
    assert result.get("ok") is True
    events = await hi.list_inbound_events(ctx_inbound_configured, ListInboundEventsParams(event_kind="no_show"))
    assert events.data.total == 1
    assert events.data.events[0].bridge_id == "br_test1"


@pytest.mark.asyncio
async def test_list_inbound_events_caps_at_max_and_prunes_oldest(ctx_inbound_configured):
    """Send more than the cap (200) worth of events at a smaller scale to
    keep the test fast -- verifies pruning logic runs without raising and
    list_inbound_events never exceeds the cap. Uses a monkeypatched cap."""
    hi._INBOUND_EVENTS_MAX_ORIG = hi._INBOUND_EVENTS_MAX
    hi._INBOUND_EVENTS_MAX = 5
    try:
        for i in range(8):
            result = await hi.receive_keragon_webhook(
                ctx_inbound_configured,
                headers={"X-Keragon-Webhook-Secret": "test-shared-secret-9f21ab"},
                body=f'{{"seq": {i}}}',
                query_params={},
            )
            assert result.get("ok") is True
        events = await hi.list_inbound_events(ctx_inbound_configured, ListInboundEventsParams(event_kind=""))
        assert events.data.total <= 5
    finally:
        hi._INBOUND_EVENTS_MAX = hi._INBOUND_EVENTS_MAX_ORIG


# ──────────────────────────────────────────────────────────────────────────
# Branch 4 -- Invalid state (wrong secret, bad URL, missing name/bridge)
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_outgoing_bridge_rejects_non_url(ctx):
    result = await ho.create_outgoing_bridge(ctx, CreateOutgoingBridgeParams(name="X", webhook_url="not-a-url"))
    assert result.status == "error"


@pytest.mark.asyncio
async def test_create_outgoing_bridge_rejects_empty_name(ctx):
    result = await ho.create_outgoing_bridge(
        ctx, CreateOutgoingBridgeParams(name="   ", webhook_url="https://hooks.keragon.com/x"),
    )
    assert result.status == "error"


@pytest.mark.asyncio
async def test_receive_keragon_webhook_wrong_secret_is_rejected(ctx_inbound_configured):
    result = await hi.receive_keragon_webhook(
        ctx_inbound_configured,
        headers={"X-Keragon-Webhook-Secret": "totally-wrong-guess"},
        body="{}",
        query_params={},
    )
    assert "error" in result
    events = await hi.list_inbound_events(ctx_inbound_configured, ListInboundEventsParams(event_kind=""))
    assert events.data.total == 0  # rejected delivery is never stored


@pytest.mark.asyncio
async def test_receive_keragon_webhook_not_configured_at_all_is_rejected(ctx):
    """Before regenerate_inbound_secret has ever been called, ANY delivery
    must be rejected -- there is no secret to compare against."""
    result = await hi.receive_keragon_webhook(
        ctx, headers={"X-Keragon-Webhook-Secret": "anything"}, body="{}", query_params={},
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_get_outgoing_bridge_unknown_id_errors(ctx):
    result = await ho.get_outgoing_bridge(ctx, GetOutgoingBridgeParams(bridge_id="does-not-exist"))
    assert result.status == "error"


@pytest.mark.asyncio
async def test_send_bridge_event_network_failure_not_raised_as_exception(ctx_with_bridge):
    """A DNS/timeout/connection-refused failure against the user's own
    Keragon workflow is an expected, reportable outcome -- not an unhandled
    exception that would surface as a raw 500 to the chat."""
    class _BoomHTTP:
        async def post(self, *a, **kw):
            raise ConnectionError("Could not resolve host")

    ctx_with_bridge.http = _BoomHTTP()
    result = await ho.send_bridge_event(
        ctx_with_bridge, SendBridgeEventParams(bridge_id="br_test1", payload={"x": 1}),
    )
    assert result.status == "error"
    assert "failed" in result.error.lower()


@pytest.mark.asyncio
async def test_send_bridge_event_non_2xx_status_is_reported_as_failure(ctx_with_bridge):
    ctx_with_bridge.http.mock_post("hooks.keragon.com", response={}, status=410)
    result = await ho.send_bridge_event(
        ctx_with_bridge, SendBridgeEventParams(bridge_id="br_test1", payload={"x": 1}),
    )
    assert result.status == "error"
    assert "410" in result.error


# ──────────────────────────────────────────────────────────────────────────
# Branch 5 -- Exotic / adversarial (soap-opera sequences, rotation, replay)
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_outgoing_bridge_partial_fields_only(ctx_with_bridge):
    """Only given fields change -- name-only update must not clobber the URL."""
    result = await ho.update_outgoing_bridge(
        ctx_with_bridge, UpdateOutgoingBridgeParams(bridge_id="br_test1", name="Renamed intake"),
    )
    assert result.status == "success"
    assert result.data.name == "Renamed intake"
    assert result.data.has_url is True  # untouched


@pytest.mark.asyncio
async def test_delete_outgoing_bridge_then_send_fails(ctx_with_bridge):
    deleted = await ho.delete_outgoing_bridge(ctx_with_bridge, DeleteOutgoingBridgeParams(bridge_id="br_test1"))
    assert deleted.data.deleted is True

    result = await ho.send_bridge_event(ctx_with_bridge, SendBridgeEventParams(bridge_id="br_test1", payload={}))
    assert result.status == "error"


@pytest.mark.asyncio
async def test_regenerate_inbound_secret_twice_old_secret_stops_working(ctx_inbound_configured):
    """D2 Idempotency / soap-opera: regenerate the secret while an old one
    is already saved -- the OLD secret must stop being accepted immediately
    after rotation."""
    old_secret = "test-shared-secret-9f21ab"

    pre = await hi.receive_keragon_webhook(
        ctx_inbound_configured,
        headers={"X-Keragon-Webhook-Secret": old_secret}, body="{}", query_params={},
    )
    assert pre.get("ok") is True

    await hi.regenerate_inbound_secret(ctx_inbound_configured, RegenerateInboundSecretParams())

    post = await hi.receive_keragon_webhook(
        ctx_inbound_configured,
        headers={"X-Keragon-Webhook-Secret": old_secret}, body="{}", query_params={},
    )
    assert "error" in post


@pytest.mark.asyncio
async def test_replay_of_same_delivery_is_recorded_twice_not_deduped(ctx_inbound_configured):
    """This app does not attempt delivery-id deduplication -- a workflow
    retry after a timeout is expected to create a second event, not
    silently vanish."""
    body = '{"event_kind": "replayed"}'
    headers = {"X-Keragon-Webhook-Secret": "test-shared-secret-9f21ab"}
    await hi.receive_keragon_webhook(ctx_inbound_configured, headers=headers, body=body, query_params={})
    await hi.receive_keragon_webhook(ctx_inbound_configured, headers=headers, body=body, query_params={})

    events = await hi.list_inbound_events(ctx_inbound_configured, ListInboundEventsParams(event_kind=""))
    assert events.data.total == 2


@pytest.mark.asyncio
async def test_bulk_send_continues_past_unknown_bridge_id(ctx_with_bridge):
    """One bad id in a bulk call must not abort the rest."""
    ctx_with_bridge.http.mock_post("hooks.keragon.com", response={}, status=200)
    result = await ho.bulk_send_bridge_event(
        ctx_with_bridge, BulkSendBridgeEventParams(bridge_ids=["br_test1", "ghost"], payload={"x": 1}),
    )
    assert result.status == "success"
    assert result.data.sent == 1
    assert result.data.total == 2


@pytest.mark.asyncio
async def test_full_lifecycle_configure_use_rotate_audit(ctx):
    """Soap-opera sequence covering the whole owner journey in one run:
    create a bridge, fire it, configure inbound, receive a callback,
    rotate the secret, then audit overall health."""
    ctx.http.mock_post("hooks.keragon.com", response={}, status=200)

    created = await ho.create_outgoing_bridge(
        ctx, CreateOutgoingBridgeParams(name="Intake", webhook_url="https://hooks.keragon.com/trigger/xyz"),
    )
    bridge_id = created.data.id

    fired = await ho.send_bridge_event(ctx, SendBridgeEventParams(bridge_id=bridge_id, payload={"k": "v"}))
    assert fired.status == "success"

    gen = await hi.regenerate_inbound_secret(ctx, RegenerateInboundSecretParams())
    secret = gen.data.detail

    recv = await hi.receive_keragon_webhook(
        ctx, headers={"X-Keragon-Webhook-Secret": secret},
        body='{"event_kind": "confirmed"}', query_params={"bridge_id": bridge_id},
    )
    assert recv.get("ok") is True

    await hi.regenerate_inbound_secret(ctx, RegenerateInboundSecretParams())
    stale = await hi.receive_keragon_webhook(
        ctx, headers={"X-Keragon-Webhook-Secret": secret}, body="{}", query_params={},
    )
    assert "error" in stale

    audit = await hv.audit_bridge_health(ctx, NoParams())
    assert audit.data.outgoing_bridge_count == 1
    assert audit.data.inbound_configured is True
    assert bridge_id not in audit.data.silent_bridges  # it DID produce a callback
