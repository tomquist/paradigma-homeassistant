"""Paradigma Modbus Hub."""
import logging
import threading
from pymodbus.client import ModbusTcpClient

_LOGGER = logging.getLogger(__name__)

class ParadigmaHub:
    def __init__(self, hass, name, host, port, slave_id):
        self._hass = hass
        self._slave_id = int(slave_id)
        self._client = ModbusTcpClient(host=host, port=port)
        self._lock = threading.Lock()
        self.name = name

    def connect(self):
        with self._lock:
            return self._client.connect()

    def close(self):
        with self._lock:
            self._client.close()

    def _read_modbus(self, func_name, address, count, unit_id=None):
        """Helper to try device_id, slave, and unit."""
        device = self._slave_id if unit_id is None else int(unit_id)
        func = getattr(self._client, func_name)
        with self._lock:
            try:
                try:
                    res = func(address=address, count=count, device_id=device)
                except TypeError:
                    try:
                        res = func(address, count, slave=device)
                    except TypeError:
                        res = func(address, count, unit=device)

                if res.isError(): return None
                return res
            except Exception:
                return None

    def read_input_registers(self, address, count, unit_id=None):
        res = self._read_modbus("read_input_registers", address, count, unit_id)
        return res.registers if res else None

    def read_holding_registers(self, address, count, unit_id=None):
        res = self._read_modbus("read_holding_registers", address, count, unit_id)
        return res.registers if res else None

    def read_coils(self, address, count, unit_id=None):
        res = self._read_modbus("read_coils", address, count, unit_id)
        return res.bits if res else None

    def write_register(self, address, value, unit_id=None):
        """Write Single Register - Forced as Multiple (FC 0x10)."""
        device = self._slave_id if unit_id is None else int(unit_id)
        with self._lock:
            try:
                try:
                    res = self._client.write_registers(address=address, values=[value], device_id=device)
                except TypeError:
                    try:
                        res = self._client.write_registers(address, [value], slave=device)
                    except TypeError:
                        res = self._client.write_registers(address, [value], unit=device)

                return not res.isError()
            except Exception as e:
                _LOGGER.error(f"Fehler beim Schreiben (Register {address}): {e}")
                return False

    def write_coil(self, address, value):
        """Write Single Coil."""
        with self._lock:
            try:
                try:
                    self._client.write_coil(address, value, device_id=self._slave_id)
                except TypeError:
                    try:
                        self._client.write_coil(address, value, slave=self._slave_id)
                    except TypeError:
                        self._client.write_coil(address, value, unit=self._slave_id)
                return True
            except Exception:
                return False
