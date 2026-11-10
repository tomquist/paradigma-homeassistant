"""One-time registry migration to the upstream V2.6.2 identifier scheme."""

import logging

from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .entity_ids import SUFFIXES

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass, entry) -> bool:
    """Preserve registry rows and public entity IDs; never access the controller.

    Registry operations and the version update are synchronous on HA's event loop
    (no awaits), so other tasks cannot interleave with preflight/application.
    The registry/config-entry stores still persist independently: take a backup.
    """
    if entry.version == 2:
        return True
    if entry.version != 1:
        _LOGGER.error("Unsupported Paradigma config version %s", entry.version)
        return False

    registry = er.async_get(hass)
    changes = []
    prefix = f"{entry.entry_id}_"
    for row in er.async_entries_for_config_entry(registry, entry.entry_id):
        if row.platform != DOMAIN or not row.unique_id.startswith(prefix):
            continue
        domain = row.entity_id.split(".", 1)[0]
        suffix = row.unique_id[len(prefix):]
        target_suffix = SUFFIXES.get(domain, {}).get(suffix)
        if target_suffix is None:
            continue
        target = prefix + target_suffix
        owner = registry.async_get_entity_id(domain, DOMAIN, target)
        if owner is not None and owner != row.entity_id:
            _LOGGER.error(
                "Paradigma migration blocked: %s conflicts with %s. "
                "No changes applied. Back up Home Assistant and resolve the "
                "duplicate registry entities before retrying; do not delete "
                "entities with history blindly.",
                row.entity_id, owner,
            )
            return False
        changes.append((row.entity_id, row.unique_id, target))

    applied = []
    original_version = entry.version
    original_minor_version = entry.minor_version
    try:
        for entity_id, old_id, new_id in changes:
            # Record first so even an API wrapper failing after mutation can
            # be rolled back. Only the unique_id field is changed.
            applied.append((entity_id, old_id, new_id))
            registry.async_update_entity(entity_id, new_unique_id=new_id)
        hass.config_entries.async_update_entry(entry, version=2, minor_version=1)
    except Exception:
        _LOGGER.exception("Paradigma migration failed; restoring previous identifiers")
        # A failing API wrapper could have committed the version before raising.
        if (entry.version, entry.minor_version) != (original_version, original_minor_version):
            try:
                hass.config_entries.async_update_entry(
                    entry, version=original_version, minor_version=original_minor_version
                )
            except Exception:
                _LOGGER.exception("Could not restore config version; restore the pre-migration backup")
        for entity_id, old_id, new_id in reversed(applied):
            try:
                row = registry.async_get(entity_id)
                if row is not None and row.unique_id == new_id:
                    registry.async_update_entity(entity_id, new_unique_id=old_id)
            except Exception:
                _LOGGER.exception(
                    "Could not restore %s; restore the pre-migration backup", entity_id
                )
        return False

    _LOGGER.info(
        "Migrated Paradigma config entry to version 2; retained entity IDs for %s entities",
        len(changes),
    )
    return True
