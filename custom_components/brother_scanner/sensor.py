import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)

from .const import DOMAIN, SCAN_INTERVAL, MODEL
from .device import get_device_info
from .api import get_scanner_state, check_online
from .diagnostics import load_diagnostics

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    ip = entry.data["ip"]
    entry_id = entry.entry_id

    coordinator = BrotherScannerCoordinator(hass, ip, entry_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry_id]["coordinator"] = coordinator

    devices = [
        BrotherScannerStateSensor(coordinator, entry),
        BrotherScannerStateReasonSensor(coordinator, entry),
        BrotherScannerAdfSensor(coordinator, entry),
        BrotherScannerOnlineSensor(coordinator, entry),
        BrotherScannerPagesSensor(coordinator, entry),
        BrotherScannerLastScanSensor(coordinator, entry),
        BrotherScannerLastPagesSensor(coordinator, entry),
    ]
    async_add_entities(devices)
    return True


class BrotherScannerCoordinator(DataUpdateCoordinator):
    """Fetch scanner status, online state and diagnostics periodically."""

    def __init__(self, hass, ip, entry_id):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{MODEL} {ip}",
            update_interval=SCAN_INTERVAL,
        )
        self.ip = ip
        self.entry_id = entry_id

    async def _async_update_data(self):
        status = await get_scanner_state(self.ip)
        online = await check_online(self.ip)
        diagnostics = await load_diagnostics(self.hass, self.entry_id)
        return {**status, "online": online, **diagnostics}


class BaseBrotherEntity(CoordinatorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._ip = coordinator.ip
        self._entry_id = entry.entry_id
        self._hostname = entry.data.get("hostname", self._ip)
        self._attr_device_info = get_device_info(self._entry_id, self._ip)
        self._attr_has_entity_name = True


class BrotherScannerStateSensor(BaseBrotherEntity, SensorEntity):
    """Current scanner state (Idle, Scanning, ...)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._entry_id}_scanner_state"
        self._attr_name = "Scanner State"
        self._attr_icon = "mdi:printer"

    @property
    def native_value(self):
        return self.coordinator.data.get("state") if self.coordinator.data else STATE_UNKNOWN


class BrotherScannerStateReasonSensor(BaseBrotherEntity, SensorEntity):
    """Detailed scanner state reason (e.g. processing, cover open)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._entry_id}_scanner_state_reason"
        self._attr_name = "Scanner State Reason"
        self._attr_icon = "mdi:information-outline"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return STATE_UNKNOWN
        return self.coordinator.data.get("state_reason")
    """Automatic document feeder state (paper present, feeder open, ...)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._entry_id}_adf_state"
        self._attr_name = "ADF State"
        self._attr_icon = "mdi:document-scan"

    @property
    def native_value(self):
        return self.coordinator.data.get("adf_state") if self.coordinator.data else STATE_UNKNOWN


class BrotherScannerOnlineSensor(BaseBrotherEntity, BinarySensorEntity):
    """Online status of the scanner (responsive on port 80)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._entry_id}_online"
        self._attr_name = "Online"
        self._attr_icon = "mdi:lan-connect"

    @property
    def is_on(self):
        return bool(self.coordinator.data and self.coordinator.data.get("online"))


class BrotherScannerPagesSensor(BaseBrotherEntity, SensorEntity):
    """Total number of pages scanned since setup."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._entry_id}_pages_scanned"
        self._attr_name = "Pages Scanned"
        self._attr_icon = "mdi:counter"
        self._attr_native_unit_of_measurement = "pages"
        self._attr_state_class = "total_increasing"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return STATE_UNKNOWN
        return int(self.coordinator.data.get("pages_scanned", 0))


class BrotherScannerLastScanSensor(BaseBrotherEntity, SensorEntity):
    """Timestamp of the last scan."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._entry_id}_last_scan"
        self._attr_name = "Last Scan"
        self._attr_icon = "mdi:calendar-clock"
        self._attr_device_class = "timestamp"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return STATE_UNKNOWN
        return self.coordinator.data.get("last_scan")


class BrotherScannerLastPagesSensor(BaseBrotherEntity, SensorEntity):
    """Number of pages in the last scan."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._entry_id}_last_pages"
        self._attr_name = "Last Scan Pages"
        self._attr_icon = "mdi:file-multiple"
        self._attr_native_unit_of_measurement = "pages"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return STATE_UNKNOWN
        return int(self.coordinator.data.get("last_pages", 0))
