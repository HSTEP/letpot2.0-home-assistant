"""Offline checks for the one-time recovery tool."""

from dataclasses import replace
import unittest

from test_protocol import device_status
from tools.repair_manual_duration import repair_status, verified


class RecoveryTests(unittest.TestCase):
    def test_repair_changes_only_duration(self):
        before = replace(device_status(), pump_manual_duration=0, pump_cycle_on=True)
        after = repair_status(before, 3)
        self.assertEqual(after, replace(before, pump_manual_duration=3))
        self.assertEqual(before.pump_manual_duration, 0)
        self.assertTrue(verified(before, after, 3))

    def test_refuses_active_or_scheduled_pump(self):
        for status in (replace(device_status(), pump_on=True),
                       replace(device_status(), pump_mode=1)):
            with self.subTest(status=status), self.assertRaises(ValueError):
                repair_status(status, 3)

    def test_rejects_invalid_duration(self):
        for minutes in (0, -1, 61):
            with self.subTest(minutes=minutes), self.assertRaises(ValueError):
                repair_status(device_status(), minutes)

    def test_readback_must_match_all_cycle_settings_and_be_idle(self):
        before = device_status()
        for field, value in (("pump_on", True), ("pump_mode", 1),
                             ("pump_manual_duration", 768), ("pump_cycle_on", True),
                             ("pump_cycle_frequency", 25), ("pump_cycle_duration", 4),
                             ("pump_cycle_mode", 1), ("pump_cycle_workinginterval", 1),
                             ("pump_cycle_restinterval", 1), ("pump_cycle_skip_water", 1)):
            with self.subTest(field=field):
                self.assertFalse(verified(before, replace(before, **{field: value}), 3))


if __name__ == "__main__":
    unittest.main()
