"""Inspect or explicitly repair a DI-3's stored manual duration; never start it."""

import argparse
import asyncio
from dataclasses import replace
from importlib.metadata import version
import json
import logging
from pathlib import Path

from letpot.converters import ISEConverter
from letpot.deviceclient import LetPotDeviceClient
from letpot.models import AuthenticationInfo, LetPotWateringSystemStatus


CYCLE_FIELDS = (
    "pump_cycle_on", "pump_cycle_frequency", "pump_cycle_duration",
    "pump_cycle_mode", "pump_cycle_workinginterval", "pump_cycle_restinterval",
    "pump_cycle_skip_water",
)


def repair_status(status, minutes):
    """Only change duration on an idle device, preserving its other settings."""
    if not isinstance(status, LetPotWateringSystemStatus):
        raise ValueError("The device did not return a watering-system status")
    if status.pump_on or status.pump_mode != 0:
        raise ValueError("Stop watering and select manual/off mode before retrying")
    if not 1 <= minutes <= 60:
        raise ValueError("Choose a manual duration between 1 and 60 minutes")
    return replace(status, pump_manual_duration=minutes)


def verified(before, after, minutes):
    return (
        isinstance(after, LetPotWateringSystemStatus)
        and after.pump_manual_duration == minutes
        and not after.pump_on and after.pump_mode == 0
        and all(getattr(before, key) == getattr(after, key) for key in CYCLE_FIELDS)
    )


async def run(args):
    if version("letpot") != "0.7.0":
        raise ValueError("Use an isolated environment with letpot==0.7.0")
    if not args.serial.startswith("ISE06"):
        raise ValueError("This recovery tool is limited to DI-3 / ISE06 devices")
    entries = json.loads(args.config.read_text())["data"]["entries"]
    entries = [e for e in entries if e.get("domain") == "letpot"
               and (not args.entry_id or e["entry_id"] == args.entry_id)]
    if len(entries) != 1:
        raise ValueError("Expected one LetPot entry; use --entry-id to select one")
    data = entries[0]["data"]
    # The device client only uses email/user ID. Never print or upload credentials.
    auth = AuthenticationInfo(
        email=data["email"], user_id=str(data["user_id"]),
        access_token="", refresh_token="",
        access_token_expires=0, refresh_token_expires=0,
    )
    client = LetPotDeviceClient(auth)
    try:
        await client.subscribe(args.serial, lambda status: None)
        before = await client.get_current_status(args.serial)
        if not isinstance(before, LetPotWateringSystemStatus):
            raise ValueError("No valid watering-system status received")
        print(f"Stored manual duration: {before.pump_manual_duration} minutes", flush=True)
        if not args.apply:
            print("Read only: no settings changed. Add --apply to write --minutes.")
            return
        target = repair_status(before, args.minutes)
        if before.pump_manual_duration == args.minutes:
            print("Already correct; no settings write needed.")
            return
        # Use the unmodified pinned encoder. There is no public duration setter in 0.7.0.
        message = ISEConverter("ISE06").get_update_status_message(target)
        await client._publish(args.serial, message)
        print("Settings write sent; verifying device readback...", flush=True)
        await asyncio.sleep(2)
        after = await client.get_current_status(args.serial)
        if not verified(before, after, args.minutes):
            raise ValueError("Readback mismatch; inspect settings in the LetPot app. No retry sent")
        print(f"Verified: {args.minutes} minutes; pump off; cycle settings unchanged.")
    finally:
        await client.unsubscribe(args.serial)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True,
                        help="Local HA .storage/core.config_entries file; never share it")
    parser.add_argument("--serial", required=True, help="Your DI-3 serial number")
    parser.add_argument("--entry-id", help="Select a LetPot config entry if several exist")
    parser.add_argument("--minutes", type=int, choices=range(1, 61), default=3,
                        metavar="1-60", help="Desired duration (default: 3 minutes)")
    parser.add_argument("--apply", action="store_true", help="Write duration with pump off")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        asyncio.run(asyncio.wait_for(run(args), timeout=45))
    except (Exception, KeyboardInterrupt) as error:
        # Exceptions from dependencies can include identifiers; do not print them.
        detail = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(f"Not verified: {detail}. If a write was sent, check the app before retrying.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
