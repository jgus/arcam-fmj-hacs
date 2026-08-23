from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    enable_custom_integrations


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
    ):
        yield
