"""Tests for the PC Remote sensor platform."""

from __future__ import annotations

from tests.conftest import (
    make_coordinator_data,
    make_mock_coordinator,
    make_mock_entry,
    wire_entity,
)

from custom_components.pc_remote.sensor import PcRemoteIdleSensor, PcRemoteVersionSensor


class TestIdleSensor:
    """Tests for PcRemoteIdleSensor."""

    def _make_sensor(self, coordinator=None, entry=None):
        entry = entry or make_mock_entry()
        coordinator = coordinator or make_mock_coordinator()
        sensor = PcRemoteIdleSensor(coordinator, entry)
        wire_entity(sensor, coordinator)
        return sensor

    def test_native_value_returns_idle_seconds(self):
        data = make_coordinator_data(idle_seconds=120)
        coordinator = make_mock_coordinator(data)
        sensor = self._make_sensor(coordinator=coordinator)
        assert sensor.native_value == 120

    def test_native_value_none_when_not_available(self):
        data = make_coordinator_data(idle_seconds=None)
        coordinator = make_mock_coordinator(data)
        sensor = self._make_sensor(coordinator=coordinator)
        assert sensor.native_value is None

    def test_available_when_online(self):
        data = make_coordinator_data(online=True)
        coordinator = make_mock_coordinator(data)
        sensor = self._make_sensor(coordinator=coordinator)
        assert sensor.available is True

    def test_unavailable_when_offline(self):
        data = make_coordinator_data(online=False)
        coordinator = make_mock_coordinator(data)
        sensor = self._make_sensor(coordinator=coordinator)
        assert sensor.available is False

    def test_unique_id(self):
        sensor = self._make_sensor()
        assert sensor.unique_id == "test_entry_id_idle_duration"

    def test_device_class(self):
        from homeassistant.components.sensor import SensorDeviceClass
        sensor = self._make_sensor()
        assert sensor.device_class == SensorDeviceClass.DURATION

    def test_native_unit(self):
        from homeassistant.const import UnitOfTime
        sensor = self._make_sensor()
        assert sensor.native_unit_of_measurement == UnitOfTime.SECONDS


class TestVersionSensor:
    """Tests for PcRemoteVersionSensor."""

    def _make_sensor(self, coordinator=None, entry=None):
        entry = entry or make_mock_entry()
        coordinator = coordinator or make_mock_coordinator()
        sensor = PcRemoteVersionSensor(coordinator, entry)
        wire_entity(sensor, coordinator)
        return sensor

    def test_version_sensor_shows_service_version(self):
        data = make_coordinator_data(service_version="1.7.0")
        coordinator = make_mock_coordinator(data)
        sensor = self._make_sensor(coordinator=coordinator)
        assert sensor.native_value == "1.7.0"

    def test_version_sensor_none_when_empty_string(self):
        data = make_coordinator_data(service_version="")
        coordinator = make_mock_coordinator(data)
        sensor = self._make_sensor(coordinator=coordinator)
        assert sensor.native_value is None

    def test_version_sensor_unavailable_when_offline(self):
        data = make_coordinator_data(online=False)
        coordinator = make_mock_coordinator(data)
        sensor = self._make_sensor(coordinator=coordinator)
        assert sensor.available is False

    def test_version_sensor_available_when_online(self):
        data = make_coordinator_data(online=True)
        coordinator = make_mock_coordinator(data)
        sensor = self._make_sensor(coordinator=coordinator)
        assert sensor.available is True

    def test_unique_id(self):
        sensor = self._make_sensor()
        assert sensor.unique_id == "test_entry_id_service_version"

    def test_entity_category_is_diagnostic(self):
        from homeassistant.const import EntityCategory
        sensor = self._make_sensor()
        assert sensor.entity_category == EntityCategory.DIAGNOSTIC
