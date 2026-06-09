"""Number platform for Paradigma."""
from homeassistant.components.number import NumberEntity, NumberDeviceClass, NumberMode
from homeassistant.const import UnitOfPower
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, CONF_HK2, CONF_EMS, EMS_UNIT_ID

NUMBERS = [
    ("setpoint_flow_hk1", 2, 20, 80, 1, False),
    ("setpoint_flow_hk2", 3, 20, 80, 1, True),
    ("setpoint_buffer_top", 44, 20, 90, 0.5, False),
    ("setpoint_boiler", 45, 20, 90, 0.5, False),
]

# EMS-Schnittstelle Wärmepumpe (Unit ID 2), nur schreibbar (FC 0x10)
# (key, address, min, max, enabled_default)
EMS_NUMBERS = [
    ("ems_pv_surplus", 0, 0, 65533, True),
    ("ems_power_limit", 3, 0, 65535, False),
]

async def async_setup_entry(hass, entry, async_add_entities):
    hub = hass.data[DOMAIN][entry.entry_id]
    entities = []
    hk2_active = entry.data.get(CONF_HK2, False)
    for n in NUMBERS:
        if n[5] and not hk2_active: continue
        entities.append(ParadigmaNumber(hub, n[0], n[1], n[2], n[3], n[4], entry))
    if entry.data.get(CONF_EMS):
        for n in EMS_NUMBERS:
            entities.append(ParadigmaEmsNumber(hub, n[0], n[1], n[2], n[3], n[4], entry))
    async_add_entities(entities)

class ParadigmaNumber(NumberEntity):
    def __init__(self, hub, key, address, min_val, max_val, step, entry):
        self._hub = hub
        self._address = address
        self._entry_id = entry.entry_id
        self._attr_has_entity_name = True
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_num_{address}"
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_value = None

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self._entry_id)}, name="Paradigma Heizung", manufacturer="Paradigma", model="SystaSmartC II")

    def update(self):
        res = self._hub.read_holding_registers(self._address, 1)
        if res and res[0] not in [0x8000, 0xFFFF]:
            self._attr_native_value = res[0] * 0.1

    def set_native_value(self, value):
        val_int = int(value * 10)
        self._hub.write_register(self._address, val_int)
        self._attr_native_value = value

class ParadigmaEmsNumber(NumberEntity):
    """Schreibbare Register der EMS-Schnittstelle (Unit ID 2).

    Die Register sind laut Doku nur schreibbar (FC 0x10), daher kein Polling –
    der Zustand entspricht dem zuletzt geschriebenen Wert.
    """
    _attr_should_poll = False

    def __init__(self, hub, key, address, min_val, max_val, enabled_default, entry):
        self._hub = hub
        self._address = address
        self._entry_id = entry.entry_id
        self._attr_has_entity_name = True
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_ems_num_{address}"
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = 1
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = NumberDeviceClass.POWER
        self._attr_mode = NumberMode.BOX
        self._attr_entity_registry_enabled_default = enabled_default

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self._entry_id)}, name="Paradigma Heizung", manufacturer="Paradigma", model="SystaSmartC II")

    def set_native_value(self, value):
        if self._hub.write_register(self._address, int(value), unit_id=EMS_UNIT_ID):
            self._attr_native_value = int(value)