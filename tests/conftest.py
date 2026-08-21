"""Shared fixtures for Keragon Connector PST (Plausible Scenario Testing).

Mirrors Zapier Webhook's tests/conftest.py: imperal_sdk.testing.MockContext
+ MockSecretStore give us the REAL handler code paths (real HTTP call
construction, real secret storage, real header-comparison logic) against a
controlled fake HTTP backend -- not a re-implementation of the logic under a
different name.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def ctx():
    from imperal_sdk.testing import MockContext, MockSecretStore

    mock = MockContext()
    mock.secrets = MockSecretStore({})
    return mock


@pytest.fixture
def ctx_with_bridge(ctx):
    """Same as `ctx` but with one outgoing bridge already registered."""
    from imperal_sdk.testing import MockSecretStore
    ctx.secrets = MockSecretStore({
        "keragon_outgoing_bridges": json.dumps([{
            "id": "br_test1",
            "name": "New patient intake",
            "description": "Fires the intake workflow",
            "webhook_url": "https://hooks.keragon.com/trigger/abc123",
            "created_at": "2026-08-21T00:00:00Z",
        }]),
    })
    return ctx


@pytest.fixture
def ctx_inbound_configured(ctx):
    """Same as `ctx` but with an inbound shared secret already generated."""
    from imperal_sdk.testing import MockSecretStore
    ctx.secrets = MockSecretStore({
        "keragon_inbound_shared_secret": "test-shared-secret-9f21ab",
    })
    return ctx


@pytest.fixture
def ctx_both_configured(ctx):
    """Both directions configured at once -- the account owner's steady state."""
    from imperal_sdk.testing import MockSecretStore
    ctx.secrets = MockSecretStore({
        "keragon_outgoing_bridges": json.dumps([{
            "id": "br_test1",
            "name": "New patient intake",
            "description": "Fires the intake workflow",
            "webhook_url": "https://hooks.keragon.com/trigger/abc123",
            "created_at": "2026-08-21T00:00:00Z",
        }]),
        "keragon_inbound_shared_secret": "test-shared-secret-9f21ab",
    })
    return ctx
