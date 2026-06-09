"""Select platform for Paradigma (EMS-Schnittstelle Unit ID 2)."""
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, CONF_EMS, EMS_UNIT_ID

# Tarifsignal (Register 2): 0 = keine Tarifsteuerung, 1 = Hochtarif, 2 = Niedertarif
TARIFF_OPTIONS = {
    "no_control": 0,
    "high_tariff": 1,
    "low_tariff": 2,
}

async def async_setup_entry(hass, entry, async_add_entities):
    hub = hass.data[DOMAIN][entry.entry_id]
    if not entry.data.get(CONF_EMS):
        return
    async_add_entities([ParadigmaTariffSelect(hub, entry)])

class ParadigmaTariffSelect(SelectEntity):
    """Tarifsignal der EMS-Schnittstelle.

    Das Register ist laut Doku nur schreibbar (FC 0x10), daher kein Polling –
    der Zustand entspricht dem zuletzt geschriebenen Wert.
    """
    _attr_should_poll = False

    def __init__(self, hub, entry):
        self._hub = hub
        self._address = 2
        self._entry_id = entry.entry_id
        self._attr_has_entity_name = True
        self._attr_translation_key = "ems_tariff_signal"
        self._attr_unique_id = f"{entry.entry_id}_ems_select_{self._address}"
        self._attr_options = list(TARIFF_OPTIONS)
        self._attr_current_option = None

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self._entry_id)}, name="Paradigma Heizung", manufacturer="Paradigma", model="SystaSmartC II")

    def select_option(self, option):
        if self._hub.write_register(self._address, TARIFF_OPTIONS[option], unit_id=EMS_UNIT_ID):
            self._attr_current_option = option
