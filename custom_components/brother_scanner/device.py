from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, MANUFACTURER, MODEL
import re


def get_device_info(entry_id: str, ip: str, model: str | None = None) -> DeviceInfo:
    """Return shared DeviceInfo for a Brother scanner."""
    model_name = model or MODEL
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=f"{model_name} {ip}",
        manufacturer=MANUFACTURER,
        model=model_name,
        configuration_url=f"http://{ip}",
    )
