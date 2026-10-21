"""Offline regression checks: python -m unittest -v test_protocol.py."""

import ast
from dataclasses import replace
from pathlib import Path
import unittest

from letpot.converters import ISEConverter
from letpot.models import CycleWateringMode, LetPotDeviceErrors, LetPotWateringSystemStatus


def device_status():
    """A DI-3 idle configuration with a three-minute manual duration."""
    return LetPotWateringSystemStatus(
        raw=[], pump_mode=0, errors=LetPotDeviceErrors(low_water=False),
        wifi_state=0, pump_on=False, pump_manual_duration=3,
        pump_cycle_on=False, pump_cycle_frequency=24, pump_cycle_duration=3,
        pump_cycle_mode=CycleWateringMode.CONTINUOUS,
        pump_cycle_workinginterval=0, pump_cycle_restinterval=0,
        pump_cycle_skip_water=0, pump_works_end=None,
        pump_works_latest_reason=2, pump_works_latest_time=None,
        pump_works_next_time=None,
    )


class ProtocolTests(unittest.TestCase):
    def test_three_minutes_remains_three_minutes(self):
        message = ISEConverter("ISE06").get_update_status_message(device_status())
        # Vendor write order: command, operation, mode, cycle flag, duration MSB/LSB.
        self.assertEqual(message, [65, 2, 0, 0, 0, 3, 0, 24, 0, 3, 0, 0, 0, 0, 0])
        self.assertEqual(int.from_bytes(bytes(message[4:6]), "big"), 3)

    def test_cycle_flag_and_high_bytes_do_not_shift_duration(self):
        status = replace(
            device_status(), pump_mode=1, pump_manual_duration=257,
            pump_cycle_on=True, pump_cycle_frequency=258, pump_cycle_duration=259,
            pump_cycle_mode=CycleWateringMode.INTERMITTENT,
            pump_cycle_workinginterval=260, pump_cycle_restinterval=261,
        )
        for model in ("ISE05", "ISE06"):
            with self.subTest(model=model):
                message = ISEConverter(model).get_update_status_message(status)
                self.assertEqual(message, [65, 2, 1, 1, 1, 1, 1, 2, 1, 3, 1, 1, 4, 1, 5])

    def test_encoding_does_not_modify_cached_configuration(self):
        status = device_status()
        before = replace(status)
        ISEConverter("ISE06").get_update_status_message(status)
        self.assertEqual(status, before)

    def test_component_does_not_replace_the_library_encoder(self):
        # Catch the original regression in the custom component, not just in its dependency.
        tree = ast.parse(Path(__file__).with_name("__init__.py").read_text())
        overrides = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Store)
            and node.attr == "get_update_status_message"
            and isinstance(node.value, ast.Name)
            and node.value.id == "ISEConverter"
        ]
        self.assertFalse(overrides, "Use the pinned library encoder; do not restore the byte-order override")


if __name__ == "__main__":
    unittest.main()
