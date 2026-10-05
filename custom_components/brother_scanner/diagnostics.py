from homeassistant.helpers import storage

from .const import STORAGE_VERSION, STORAGE_KEY_TEMPLATE

DEFAULT_DIAGNOSTICS = {"pages_scanned": 0, "last_scan": None, "last_pages": 0}


async def load_diagnostics(hass, entry_id: str) -> dict:
    store = storage.Store(
        hass, STORAGE_VERSION, STORAGE_KEY_TEMPLATE.format(entry_id=entry_id)
    )
    data = await store.async_load()
    data = {**DEFAULT_DIAGNOSTICS, **(data or {})}
    display = {k: v for k, v in data.items() if k != "last_snapshot"}
    return display


async def save_diagnostics(hass, entry_id: str, data: dict) -> None:
    store = storage.Store(
        hass, STORAGE_VERSION, STORAGE_KEY_TEMPLATE.format(entry_id=entry_id)
    )
    existing = await store.async_load() or {}
    merged = {**existing, **data}
    await store.async_save(merged)


async def save_last_snapshot(hass, entry_id: str, path: str) -> None:
    """Persist the last snapshot path without overwriting diagnostics."""
    store = storage.Store(
        hass, STORAGE_VERSION, STORAGE_KEY_TEMPLATE.format(entry_id=entry_id)
    )
    existing = await store.async_load() or {}
    await store.async_save({**existing, "last_snapshot": path})
