"""Offline unit tests: focused HA API doubles, not hardware/HA integration tests.

Run: python3 -m unittest discover -s tests -v
Modules are loaded into an isolated namespace without importing the integration's
__init__ or installing Home Assistant. The doubles expose the public API surface
used by migration, but cannot prove compatibility with a running HA release.
"""

import ast
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components" / "paradigma"


def load(name):
    spec = importlib.util.spec_from_file_location(f"bridge_test.{name}", SOURCE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


package = ModuleType("bridge_test")
package.__path__ = [str(SOURCE)]
const = ModuleType("bridge_test.const")
const.DOMAIN = "paradigma"
helpers = ModuleType("homeassistant.helpers")
er = ModuleType("homeassistant.helpers.entity_registry")
er.async_get = lambda hass: hass.registry
er.async_entries_for_config_entry = lambda registry, entry_id: [
    row for row in registry.rows.values() if row.config_entry_id == entry_id
]
helpers.entity_registry = er
with patch.dict(sys.modules, {
    "bridge_test": package, "bridge_test.const": const,
    "homeassistant": ModuleType("homeassistant"), "homeassistant.helpers": helpers,
    "homeassistant.helpers.entity_registry": er,
}):
    ids = load("entity_ids")
    migration = load("migration")


class Registry:
    def __init__(self, rows):
        self.rows = {row.entity_id: row for row in rows}
        self.calls = []
        self.fail_at = None
        self.fail_after_mutation = False

    def async_get(self, entity_id):
        return self.rows.get(entity_id)

    def async_get_entity_id(self, domain, platform, unique_id):
        return next((row.entity_id for row in self.rows.values()
                     if row.entity_id.split(".")[0] == domain
                     and row.platform == platform and row.unique_id == unique_id), None)

    def async_update_entity(self, entity_id, *, new_unique_id):
        self.calls.append((entity_id, new_unique_id))
        fail = len(self.calls) == self.fail_at
        if fail and not self.fail_after_mutation:
            raise RuntimeError("simulated registry failure")
        row = self.rows[entity_id]
        owner = self.async_get_entity_id(row.entity_id.split(".")[0], row.platform, new_unique_id)
        if owner is not None and owner != entity_id:
            raise ValueError("duplicate unique_id")
        # Real registry rows are immutable and replaced rather than mutated.
        updated = copy.copy(row)
        updated.unique_id = new_unique_id
        self.rows[entity_id] = updated
        if fail:
            raise RuntimeError("simulated post-mutation failure")
        return updated


class ConfigEntries:
    def __init__(self):
        self.fail = False
        self.after = False
        self.calls = []

    def async_update_entry(self, entry, **changes):
        self.calls.append(changes)
        fail = self.fail
        self.fail = False
        if fail and not self.after:
            raise RuntimeError("simulated version failure")
        for key, value in changes.items():
            setattr(entry, key, value)
        if fail:
            raise RuntimeError("simulated post-version failure")


def row(domain, suffix, *, entry_id="entry", platform="paradigma", name=None):
    return SimpleNamespace(
        entity_id=f"{domain}.{name or suffix}", unique_id=f"{entry_id}_{suffix}",
        platform=platform, config_entry_id=entry_id, name="My custom name",
        icon="mdi:heat-pump", device_id="device", disabled_by="user", hidden_by="user",
        area_id="cellar", labels={"heating"}, options={"sensor": {"display_precision": 2}},
        id=f"registry-{domain}-{name or suffix}",
    )


class MigrationTests(unittest.TestCase):
    def setup_case(self, rows, version=1):
        self.entry = SimpleNamespace(
            entry_id="entry", version=version, minor_version=1,
            data={"host": "controller.local", "port": 502, "slave_id": 1,
                  "name": "My heating", "ems_installed": True, "hk2_installed": False,
                  "solar_installed": False, "scan_interval": 45, "unknown": "retain"},
            options={"scan_interval": 60, "unrelated": True},
        )
        self.hass = SimpleNamespace(registry=Registry(rows), config_entries=ConfigEntries())
        return self.hass.registry

    def run_migration(self):
        return asyncio.run(migration.async_migrate_entry(self.hass, self.entry))

    def test_all_mappings_preserve_entity_ids_and_metadata_and_data(self):
        rows = [row(domain, old) for domain, mapping in ids.SUFFIXES.items() for old in mapping]
        reg = self.setup_case(rows)
        before = copy.deepcopy(reg.rows)
        entry_before = copy.deepcopy(vars(self.entry))
        self.assertTrue(self.run_migration())
        self.assertEqual(self.entry.version, 2)
        for entity_id, original in before.items():
            actual = reg.rows[entity_id]
            domain = entity_id.split(".")[0]
            suffix = original.unique_id[len("entry_"):]
            self.assertEqual(actual.unique_id, "entry_" + ids.SUFFIXES[domain][suffix])
            self.assertEqual({k: v for k, v in vars(actual).items() if k != "unique_id"},
                             {k: v for k, v in vars(original).items() if k != "unique_id"})
        for field in ("data", "options", "entry_id"):
            self.assertEqual(getattr(self.entry, field), entry_before[field])

    def test_unrelated_and_unsupported_rows_are_untouched(self):
        rows = [row("sensor", "input_0", entry_id="other"),
                row("sensor", "input_1", platform="other"),
                row("number", "num_44"), row("number", "num_45"),
                row("switch", "switch_1"), row("water_heater", "wh_ww"),
                row("sensor", "custom_unknown"), row("sensor", "input_2")]
        rows[-1].unique_id = "not_this_entry_input_2"
        reg = self.setup_case(rows)
        before = copy.deepcopy(reg.rows)
        self.assertTrue(self.run_migration())
        self.assertEqual(reg.rows, before)
        self.assertEqual(reg.calls, [])

    def test_collision_preflight_is_atomic_including_other_config_entry(self):
        for other_entry in (False, True):
            with self.subTest(other_entry=other_entry):
                target = row("sensor", "outdoor_temp", name="existing_upstream")
                if other_entry:
                    target.config_entry_id = "another"
                reg = self.setup_case([row("sensor", "input_1"), row("sensor", "input_0"), target])
                before = copy.deepcopy(reg.rows)
                self.assertFalse(self.run_migration())
                self.assertEqual(reg.rows, before)
                self.assertEqual(reg.calls, [])
                self.assertEqual(self.entry.version, 1)
                self.assertEqual(self.hass.config_entries.calls, [])

    def test_partially_migrated_rows_and_repeat(self):
        reg = self.setup_case([row("sensor", "outdoor_temp"), row("number", "ems_num_0")])
        self.assertTrue(self.run_migration())
        self.assertEqual(reg.rows["number.ems_num_0"].unique_id, "entry_num_0_u2")
        before = copy.deepcopy(reg.rows)
        calls = len(reg.calls)
        self.assertTrue(self.run_migration())
        self.assertEqual(reg.rows, before)
        self.assertEqual(len(reg.calls), calls)

    def test_registry_failure_rolls_back_and_retry_succeeds(self):
        for after in (False, True):
            with self.subTest(after=after):
                reg = self.setup_case([row("sensor", "input_0"), row("number", "ems_num_0")])
                before = copy.deepcopy(reg.rows)
                reg.fail_at = 2
                reg.fail_after_mutation = after
                self.assertFalse(self.run_migration())
                self.assertEqual(reg.rows, before)
                self.assertEqual(self.entry.version, 1)
                self.assertTrue(self.run_migration())

    def test_version_update_failure_rolls_back(self):
        for after in (False, True):
            with self.subTest(after=after):
                reg = self.setup_case([row("sensor", "input_0")])
                before = copy.deepcopy(reg.rows)
                self.hass.config_entries.fail = True
                self.hass.config_entries.after = after
                self.assertFalse(self.run_migration())
                self.assertEqual(reg.rows, before)
                self.assertEqual(self.entry.version, 1)
                self.assertEqual(self.entry.minor_version, 1)
                self.assertTrue(self.run_migration())

    def test_supported_and_future_versions(self):
        for version, expected in ((0, False), (2, True), (3, False)):
            with self.subTest(version=version):
                reg = self.setup_case([row("sensor", "input_0")], version)
                self.assertEqual(self.run_migration(), expected)
                self.assertEqual(reg.calls, [])
                self.assertEqual(self.entry.version, version)

    def test_empty_registry(self):
        self.setup_case([])
        self.assertTrue(self.run_migration())
        self.assertEqual(self.entry.version, 2)


class IdentifierTests(unittest.TestCase):
    def test_pinned_upstream_fixture(self):
        fixture = json.loads((ROOT / "tests/fixtures/upstream_v2_6_2.json").read_text())
        self.assertEqual(ids.SUFFIXES, fixture["expected_legacy_mappings"])
        self.assertTrue(fixture["commit"].startswith("5db9299"))
        self.assertEqual(len(fixture["commit"]), 40)
        self.assertTrue(set(ids.SENSOR_SUFFIXES.values()).issubset(fixture["sensor_keys"]))
        self.assertEqual(set(ids.NUMBER_SUFFIXES.values()), set(fixture["number_suffixes"]))
        self.assertEqual(set(ids.SELECT_SUFFIXES.values()), set(fixture["select_suffixes"]))
        self.assertEqual(len(ids.SENSOR_SUFFIXES), len(set(ids.SENSOR_SUFFIXES.values())))

    def test_every_fork_sensor_has_runtime_mapping(self):
        tree = ast.parse((SOURCE / "sensor.py").read_text())
        definitions = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == "SENSOR_DEFINITIONS"
                                   for t in n.targets))
        suffixes = {f"{n.elts[4].value}_{n.elts[5].value}" for n in definitions.elts}
        self.assertEqual(suffixes, set(ids.SENSOR_SUFFIXES))
        self.assertEqual(ids.bridge_unique_id("new-entry", "sensor", "ems_7"),
                         "new-entry_ems_heater_power")
        self.assertEqual(ids.bridge_unique_id("new-entry", "number", "num_44"),
                         "new-entry_num_44")

    def test_runtime_constructors_use_helper(self):
        # Execute only __init__ with light entity base classes: catches a runtime
        # constructor still generating the old IDs without loading HA platforms.
        class Entity:
            pass
        class Power:
            POWER = "power"
        class Mode:
            BOX = "box"
        for filename, classes, cases in (
            ("number.py", ["ParadigmaNumber", "ParadigmaEmsNumber"], [
                ("ParadigmaNumber", [None, "flow", 2, 20, 80, 1], "entry_num_2_u1"),
                ("ParadigmaNumber", [None, "buffer", 44, 20, 90, 1], "entry_num_44"),
                ("ParadigmaEmsNumber", [None, "ems", 0, 0, 65533, True], "entry_num_0_u2"),
            ]),
            ("select.py", ["ParadigmaTariffSelect"], [
                ("ParadigmaTariffSelect", [None], "entry_select_tariff_u2"),
            ]),
        ):
            tree = ast.parse((SOURCE / filename).read_text())
            bodies = []
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name in classes:
                    node.body = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"]
                    node.bases = [ast.Name(id="Entity", ctx=ast.Load())]
                    bodies.append(node)
            module = ast.fix_missing_locations(ast.Module(body=bodies, type_ignores=[]))
            env = dict(Entity=Entity, bridge_unique_id=ids.bridge_unique_id,
                       UnitOfPower=SimpleNamespace(WATT="W"), NumberDeviceClass=Power,
                       NumberMode=Mode, TARIFF_OPTIONS={"no_control": 0})
            exec(compile(module, filename, "exec"), env)
            for cls, args, expected in cases:
                obj = env[cls](*args, SimpleNamespace(entry_id="entry"))
                self.assertEqual(obj._attr_unique_id, expected)
        # Sensor constructor uses coordinator/entity plumbing: check its exact
        # assignment expression with realistic instance fields instead.
        tree = ast.parse((SOURCE / "sensor.py").read_text())
        assignment = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Attribute) and t.attr == "_attr_unique_id" for t in n.targets))
        expr = ast.Expression(assignment.value)
        for suffix, target in ids.SENSOR_SUFFIXES.items():
            kind, offset = suffix.rsplit("_", 1)
            env = dict(bridge_unique_id=ids.bridge_unique_id, entry=SimpleNamespace(entry_id="entry"),
                       self=SimpleNamespace(_type=kind, _reg_idx=int(offset)))
            self.assertEqual(eval(compile(expr, "sensor.py", "eval"), env), "entry_" + target)

    def test_flow_version_and_hook(self):
        tree = ast.parse((SOURCE / "config_flow.py").read_text())
        flow = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ConfigFlow")
        version = next(n.value.value for n in flow.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets))
        self.assertEqual(version, 2)
        tree = ast.parse((SOURCE / "__init__.py").read_text())
        self.assertTrue(any(isinstance(n, ast.ImportFrom) and n.module == "migration"
                            and any(a.name == "async_migrate_entry" for a in n.names) for n in tree.body))


if __name__ == "__main__":
    unittest.main()
