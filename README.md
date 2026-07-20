# LetPot Watering Systems Integration for Home Assistant

This custom component adds support for LetPot watering systems (such as the **LetPot DI-3** watering valve) to Home Assistant. 

It is based on the official Home Assistant LetPot integration (which currently only supports hydroponic gardens), but has been extended to support watering systems and includes critical fixes to prevent device configuration corruption.

## Features
- **ON/OFF Switch (`switch.letpot`)**: Turns the physical water pump on and off instantly.
- **Running Sensor (`binary_sensor.letpot_running`)**: Indicates if the water pump is actively pumping water.
- **Protocol Fix**: Includes an internal runtime monkey-patch that corrects parameter byte alignment issues in the communication layer, making MQTT updates 100% stable.

---

## Installation

### 1. Copy Files
Copy the `letpot` directory containing this integration into your Home Assistant's `custom_components/` directory:
```text
config/custom_components/letpot/
```

### 2. Restart Home Assistant
Go to **Developer Tools -> YAML** and click **Restart** to load the custom integration.

### 3. Add Integration
1. Go to **Settings -> Devices & Services -> Add Integration**.
2. Search for **LetPot** and select it.
3. Sign in with your LetPot mobile app credentials (email and password).
4. Your watering system will be discovered and added automatically!

---

## Recommended Setup (Timers and Scheduling)

Because device-offline schedules can be unreliable on the physical valve's firmware, we recommend managing watering duration and schedules directly inside Home Assistant using native helpers and automations.

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
