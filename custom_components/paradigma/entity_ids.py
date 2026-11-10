"""Stable identifiers for the bridge to upstream V2.6.2.

Only unique IDs change; public entity IDs must never be regenerated.
Kept separate from platform modules to avoid imports during migration.
"""

SENSOR_SUFFIXES = {
    "input_0": "outdoor_temp",
    "input_1": "flow_hk1",
    "input_2": "return_hk1",
    "input_3": "dhw_temp",
    "input_4": "buffer_top",
    "input_5": "buffer_bottom",
    "input_6": "circ_return_temp",
    "input_9": "room_temp_hk1",
    "input_10": "room_temp_hk2",
    "input_7": "flow_hk2",
    "input_8": "return_hk2",
    "input_12": "boiler_flow",
    "input_13": "boiler_return",
    "holding_32_27": "boiler_hours",
    "holding_32_29": "boiler_starts",
    "input_14": "wood_flow",
    "input_15": "wood_return",
    "input_16": "wood_buffer_top",
    "holding_32_31": "pellet_hours",
    "input_11": "collector_temp",
    "holding_19": "solar_power",
    "holding_20": "solar_day",
    "holding_32_21": "solar_total",
    "input_19": "pool_temp",
    "input_20": "pool_flow",
    "input_21": "pool_return",
    "holding_status_ww_34": "status_ww",
    "holding_status_circ_35": "status_circ",
    "holding_status_hk_36": "status_hk1",
    "holding_status_hk_37": "status_hk2",
    "holding_status_solar_39": "status_solar",
    "holding_status_pool_40": "status_pool",
    "holding_status_boiler_41": "status_boiler",
    "holding_status_pellet_42": "status_pellet",
    "holding_status_wood_43": "status_wood",
    "ems_1": "ems_hp_power",
    "ems_7": "ems_heater_power",
    "ems_model_4": "ems_model_id",
    "ems_version_5": "ems_sw_version",
}

NUMBER_SUFFIXES = {
    "num_2": "num_2_u1",
    "num_3": "num_3_u1",
    "ems_num_0": "num_0_u2",
    "ems_num_3": "num_3_u2",
}
SELECT_SUFFIXES = {"ems_select_2": "select_tariff_u2"}
SUFFIXES = {
    "sensor": SENSOR_SUFFIXES,
    "number": NUMBER_SUFFIXES,
    "select": SELECT_SUFFIXES,
}


def bridge_unique_id(entry_id: str, domain: str, legacy_suffix: str) -> str:
    """Use the upstream ID where a counterpart exists, otherwise retain the ID."""
    return f"{entry_id}_{SUFFIXES.get(domain, {}).get(legacy_suffix, legacy_suffix)}"
