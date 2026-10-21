# Changelog

## Recovery documentation (after 1.0.1)

- Add step-by-step recovery for a device with a stored manual duration of zero.
- Add an optional DI-3 terminal recovery tool: read-only by default, explicit duration write, idle-state guard, and device readback verification.
- Add four offline recovery tests. The installed component and the v1.0.1 component ZIP are unchanged.

## 1.0.1 — 2026-10-21

- Removed the custom runtime override of `ISEConverter.get_update_status_message`. It placed manual-duration bytes before the cycle-enabled flag, corrupting the duration on the tested DI-3.
- Restored use of the standard encoder from the existing `letpot==0.7.0` dependency. A three-minute write was verified by reading three minutes back from the device, with its pump off and cycle settings unchanged.
- Added offline protocol regression tests, including the original three-minute case, high-byte values, cycle-enabled ordering, and a guard against restoring the override.
- Corrected installation instructions and documented how to recover a device duration already stored incorrectly. A full HA restart is required, and the HA helper timer does not replace the device's manual-duration setting.

Hardware validation is limited to the tested DI-3. This release does not add missing watering-parameter entities or change authentication behavior.

## 1.0.0

Initial custom component with watering-system pump control and running-state support.
