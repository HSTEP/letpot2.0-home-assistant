# LetPot Watering Systems Integration for Home Assistant

This custom component adds support for LetPot watering systems (such as the **LetPot DI-3** watering valve) to Home Assistant. 

This custom component is based on the Home Assistant LetPot integration and uses `letpot==0.7.0` for device communication. It has been tested with the DI-3 watering system.

## Features
- **ON/OFF Switch (`switch.letpot`)**: Turns the physical water pump on and off instantly.
- **Running Sensor (`binary_sensor.letpot_running`)**: Indicates if the water pump is actively pumping water.
- **Correct protocol encoding**: Uses the standard `letpot` library encoder without the incorrect byte-order override shipped in version 1.0.0.

---

## Installation

### 1. Copy Files
Download the component ZIP from [Releases](https://github.com/HSTEP/letpot2.0-home-assistant/releases), extract it, and copy its `letpot` folder into your Home Assistant configuration directory under `custom_components/`:

If downloading the source repository instead, its Python files, `manifest.json`, and `strings.json` are at the repository root. Copy those files into a folder named `letpot`; do not copy the repository folder under its original name. The final path must be:
```text
config/custom_components/letpot/
```

### 2. Restart Home Assistant
Perform a full **Restart Home Assistant** from Settings. A YAML reload or integration reload does not replace the already imported Python code.

### 3. Add Integration
1. Go to **Settings -> Devices & Services -> Add Integration**.
2. Search for **LetPot** and select it.
3. Sign in with your LetPot mobile app credentials (email and password).
4. Your watering system will be discovered and added automatically!

---

## Upgrading from 1.0.0 / pump stops after 1–3 seconds

Version **1.0.1** removes an incorrect runtime override of `ISEConverter.get_update_status_message`. The override moved the manual-duration bytes before the cycle-enabled flag. On the tested DI-3, this shifted the value written to the device: a requested duration of 3 minutes was read back as 768 minutes. The device was also found with a manual duration of 0, which was consistent with the short-stop symptom.

The standard encoder in `letpot==0.7.0` uses the correct field order for the tested device. This update does not change that library or any other integration functionality.

1. Back up your existing `custom_components/letpot` folder.
2. Replace the component files with version 1.0.1 and fully restart Home Assistant.
3. Check the **manual watering duration stored in the device**, using the official LetPot app, and restore a positive value such as 3 minutes. Updating the integration alone does not repair a value already stored incorrectly in the pump.
4. Keep your HA helper duration consistent with the intended run length. A helper set to 3 minutes cannot keep the pump running when the device's own duration is 0.
5. Test one watering run while present. Do not assume that a short stop always has this cause; water supply, tubing, and pump faults may produce similar symptoms.

Validation for this fix: the DI-3 accepted the standard encoder's write, device readback confirmed 3 manual minutes with the pump off and cycle settings unchanged, and the patched integration loaded after a full HA restart. Other models and firmware versions have not been verified here.

Existing unavailable watering-parameter entities are not repaired by this release. The custom component does not currently create those parameter sensors/controls; this fix addresses command encoding.

### Restore the stored duration (one-time recovery)

The update fixes future commands; it does not automatically rewrite persistent settings in the pump. There is no universal safe watering duration, so the component must not silently set everyone's device to 3 minutes.

First install 1.0.1 and fully restart HA. Temporarily disable HA watering automations and leave the pump stopped while changing settings.

**Using the LetPot mobile app:** open the affected watering device, select its manual watering controls, change the manual run duration to the time you actually want (for example, **3 minutes**), and save/confirm the setting if the app offers that control. Return to the screen and check that the duration remains correct. App labels differ by version. If your app only offers an immediate start, or does not let you save a duration, use the terminal recovery below instead. Changing only HA's `input_number.letpot_manual_duration` does not change the device's stored duration.

**Using a terminal:** a separate recovery script is included in `tools/repair_manual_duration.py` in the source repository. It uses the existing HA LetPot account locally to contact `broker.letpot.net`. It does not print credentials or start watering. By default it only reads status; writing requires `--apply`. Use a Python 3.11+ terminal with access to your HA configuration and an isolated environment, not HA's managed Python environment:

```sh
git clone https://github.com/HSTEP/letpot2.0-home-assistant.git
cd letpot2.0-home-assistant
python3 -m venv .venv-repair
. .venv-repair/bin/activate
python -m pip install 'letpot==0.7.0'

# Replace the path and YOUR_DI3_SERIAL with your own values.
# First read the current duration; this does not change settings.
python tools/repair_manual_duration.py \
  --config /config/.storage/core.config_entries \
  --serial YOUR_DI3_SERIAL

# Then explicitly set the intended duration, for example 3 minutes.
python tools/repair_manual_duration.py \
  --config /config/.storage/core.config_entries \
  --serial YOUR_DI3_SERIAL --minutes 3 --apply
```

Use the serial from your device/app. The configuration path depends on your installation; `/config` or `/homeassistant` are common mounts. Keep `.storage/core.config_entries` private; do not upload it or paste it into an issue. If there are several LetPot entries, select the appropriate one with `--entry-id`.

The tool only allows DI-3/ISE06, refuses to write while the pump is running or its mode is not manual/off, and preserves the current cycle settings. Success must say **`Verified: 3 minutes; pump off; cycle settings unchanged.`** (or your chosen duration). A timeout or mismatch is not confirmation of success; check the app before retrying. Its encoding follows the DI-3 repair verified for this release; the helper itself has offline tests and has not been separately run against other users' hardware.

Finally, set your HA helper to the intended duration, test one watering run while present, and re-enable your automations. Do not factory-reset or remove the device as a first recovery step.

## Tests

The regression checks use the pinned device library and do not connect to a device:

```sh
python -m pip install 'letpot==0.7.0'
python -m unittest -v test_protocol.py
python -m unittest -v tools.test_repair_manual_duration
```

## Recommended Setup (Timers and Scheduling)

You can manage start times and an additional turn-off timer using native Home Assistant helpers and automations. The device also has its own manual watering duration; the HA timer does not replace it. Set the device duration in the official LetPot app to the intended run length before using these automations.

### 1. Create Helpers
Go to **Settings -> Devices & Services -> Helpers** and create:
- `input_number.letpot_manual_duration` (Type: Number): Name it `Watering Duration` (e.g., 1 to 60 minutes).
- `input_datetime.letpot_start_time` (Type: Date/Time, select **Time only**): Name it `Watering Start Time`.
- `input_boolean.letpot_auto_watering` (Type: Toggle): Name it `Auto Watering Switch`.

### 2. Create Automations

#### Automation A: Automatic Turn-off Timer
This automation ensures the valve automatically turns off after running for the duration set on your helper:
```yaml
alias: "LetPot: Automatic turn-off"
description: "Turns off the LetPot valve after the configured duration runs out"
trigger:
  - platform: state
    entity_id: switch.letpot
    to: "on"
action:
  - delay:
      minutes: "{{ states('input_number.letpot_manual_duration') | int }}"
  - service: switch.turn_off
    target:
      entity_id: switch.letpot
mode: restart
```

#### Automation B: Daily Scheduled Watering
This automation triggers watering at the time configured via your helper:
```yaml
alias: "LetPot: Scheduled watering"
description: "Triggers watering at the configured start time if scheduler is enabled"
trigger:
  - platform: time
    at: input_datetime.letpot_start_time
condition:
  - condition: state
    entity_id: input_boolean.letpot_auto_watering
    state: "on"
action:
  - service: switch.turn_on
    target:
      entity_id: switch.letpot
```
