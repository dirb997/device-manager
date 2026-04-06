from __future__ import annotations

import json
import platform
import re
import subprocess
import shutil
from datetime import datetime
from typing import Any, Iterable, List

from .models import Device, DeviceStatus


def _run_command(cmd: list[str], timeout: int = 5) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def _make_device(
    *,
    device_id: str,
    name: str,
    imei: str,
    connection_type: str,
    battery_level: int = 0,
    is_charging: bool = False,
    battery_display: str = "",
) -> Device:
    now = datetime.utcnow()
    if not battery_display:
        battery_display = "No battery input" if connection_type == "bluetooth" else (f"{battery_level}%" if battery_level > 0 else "")
    return Device(
        id=device_id,
        name=name,
        imei=imei,
        connection_type=connection_type,
        status=DeviceStatus.CONNECTED,
        battery_level=battery_level,
        battery_display=battery_display,
        is_charging=is_charging,
        last_seen=now,
        connected_at=now,
    )


def _parse_android_battery(serial: str) -> tuple[int, bool]:
    """Return Android battery level + charging state via adb, fallback to (0, False)."""
    result = _run_command(["adb", "-s", serial, "shell", "dumpsys", "battery"], timeout=6)
    if not result or result.returncode != 0:
        return (0, False)

    level = 0
    is_charging = False

    for raw_line in result.stdout.splitlines():
        line = raw_line.strip().lower()
        if line.startswith("level:"):
            try:
                level = int(line.split(":", 1)[1].strip())
            except ValueError:
                level = 0
        elif line.startswith("status:"):
            # Android BatteryManager status: 2=charging, 5=full
            try:
                status_code = int(line.split(":", 1)[1].strip())
                is_charging = status_code in (2, 5)
            except ValueError:
                is_charging = False
        elif line.startswith("ac powered:") or line.startswith("usb powered:"):
            if line.endswith("true"):
                is_charging = True

    if level < 0:
        level = 0
    if level > 100:
        level = 100

    return (level, is_charging)


def _parse_apple_battery(serial: str) -> tuple[int, bool]:
    """Return iOS battery via ideviceinfo if available, fallback to (0, False)."""
    if not serial:
        return (0, False)

    serial_raw = serial.strip()
    serial_nodash = serial_raw.replace("-", "")
    serial_dash = serial_raw
    if "-" not in serial_nodash and len(serial_nodash) > 8:
        serial_dash = f"{serial_nodash[:8]}-{serial_nodash[8:]}"

    candidates = [serial_raw, serial_nodash, serial_dash]
    # Preserve order and remove duplicates/empties.
    serial_candidates = [s for i, s in enumerate(candidates) if s and s not in candidates[:i]]

    # Requires libimobiledevice (`ideviceinfo`) and trusted pairing.
    level = 0
    is_charging = False

    for udid in serial_candidates:
        level_result = _run_command(
            ["ideviceinfo", "-u", udid, "-q", "com.apple.mobile.battery", "-k", "BatteryCurrentCapacity"],
            timeout=5,
        )
        charging_result = _run_command(
            ["ideviceinfo", "-u", udid, "-q", "com.apple.mobile.battery", "-k", "BatteryIsCharging"],
            timeout=5,
        )

        if level_result and level_result.returncode == 0:
            text = level_result.stdout.strip()
            try:
                level = int(text)
            except ValueError:
                level = 0

        if charging_result and charging_result.returncode == 0:
            text = charging_result.stdout.strip().lower()
            is_charging = text in {"true", "1", "yes"}

        if level_result and level_result.returncode == 0:
            break

    if level < 0:
        level = 0
    if level > 100:
        level = 100

    return (level, is_charging)


def discover_android_devices() -> List[Device]:
    """Discover Android devices via ADB and map them to Device records."""
    result = _run_command(["adb", "devices", "-l"], timeout=5)
    if not result:
        return []

    if result.returncode != 0:
        return []

    devices: List[Device] = []

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices attached"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        serial = parts[0]
        state = parts[1]

        # Only online/ready devices should be marked as connected.
        if state != "device":
            continue

        model = "Android Device"
        for part in parts[2:]:
            if part.startswith("model:"):
                model = part.split("model:", 1)[1].replace("_", " ").strip() or model
                break

        battery_level, is_charging = _parse_android_battery(serial)

        devices.append(
            _make_device(
                device_id=f"adb-{serial}",
                name=model,
                imei=serial,
                connection_type="usb",
                battery_level=battery_level,
                is_charging=is_charging,
            )
        )

    return devices


def _walk_usb_items(items: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for item in items:
        yield item
        child_items = item.get("_items")
        if isinstance(child_items, list):
            yield from _walk_usb_items(child_items)


def discover_apple_mobile_devices() -> List[Device]:
    """Discover iPhone/iPad devices connected to macOS via USB."""
    if platform.system() != "Darwin":
        return []

    result = _run_command(["system_profiler", "SPUSBDataType", "-json"], timeout=8)
    if not result:
        return []

    if result.returncode != 0:
        return []

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    usb_roots = payload.get("SPUSBDataType", [])
    if not isinstance(usb_roots, list):
        return []

    devices: List[Device] = []
    keywords = ("iphone", "ipad", "ipod")

    for item in _walk_usb_items(usb_roots):
        name = str(item.get("_name", "")).strip()
        if not name:
            continue

        name_lc = name.lower()
        if not any(k in name_lc for k in keywords):
            continue

        serial = str(item.get("serial_num", "")).strip()
        location_id = str(item.get("location_id", "")).strip()
        identifier = serial or location_id or name.replace(" ", "-").lower()
        battery_level, is_charging = _parse_apple_battery(serial)

        devices.append(
            _make_device(
                device_id=f"apple-{identifier}",
                name=name,
                imei=serial or identifier,
                connection_type="usb",
                battery_level=battery_level,
                is_charging=is_charging,
            )
        )

    return devices


def discover_macos_usb_devices() -> List[Device]:
    """Fallback USB discovery on macOS using ioreg output parsing."""
    if platform.system() != "Darwin":
        return []

    result = _run_command(["ioreg", "-p", "IOUSB", "-l", "-w", "0"], timeout=8)
    if not result:
        return []

    if result.returncode != 0:
        return []

    devices: List[Device] = []

    blocks = result.stdout.split("+-o ")
    for block in blocks:
        if "<class IOUSBHostDevice" not in block:
            continue

        # First line looks like: "Anker USB-C Hub Device@00100000  <class IOUSBHostDevice, ...>"
        header = block.splitlines()[0].strip() if block.splitlines() else ""
        raw_name = header.split("@", 1)[0].strip()
        if not raw_name:
            continue

        # Skip noisy infrastructure/containers.
        name_lc = raw_name.lower()
        if any(skip in name_lc for skip in ("controller", "bridge", "hub")):
            continue

        serial_match = re.search(r'"(?:kUSBSerialNumberString|USB Serial Number)"\s*=\s*"([^"]+)"', block)
        serial = serial_match.group(1).strip() if serial_match else ""

        location_match = re.search(r'"locationID"\s*=\s*(\d+)', block)
        location = location_match.group(1).strip() if location_match else ""

        identifier = serial or location or raw_name.replace(" ", "-").lower()
        battery_level = 0
        is_charging = False
        if any(k in name_lc for k in ("iphone", "ipad", "ipod")):
            battery_level, is_charging = _parse_apple_battery(serial)

        devices.append(
            _make_device(
                device_id=f"usb-{identifier}",
                name=raw_name,
                imei=serial or identifier,
                connection_type="usb",
                battery_level=battery_level,
                is_charging=is_charging,
            )
        )

    # Deduplicate by ID if ioreg repeats entries.
    unique: dict[str, Device] = {d.id: d for d in devices}
    return list(unique.values())


def discover_wifi_devices() -> List[Device]:
    """Discover nearby Wi-Fi devices from the local ARP cache on macOS."""
    if platform.system() != "Darwin":
        return []

    arp_command = shutil.which("arp") or "/usr/sbin/arp"
    result = _run_command([arp_command, "-a"], timeout=5)
    if not result or result.returncode != 0:
        return []

    devices: List[Device] = []
    seen_ids: set[str] = set()

    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        match = re.search(r"\(([^)]+)\) at ([0-9a-f:]+|\(incomplete\))", line, re.IGNORECASE)
        if not match:
            continue

        ip_address = match.group(1).strip()
        mac_address = match.group(2).strip().lower()
        if mac_address == "(incomplete)" or mac_address == "00:00:00:00:00:00":
            continue

        hostname_match = re.match(r"^(.*?)\s*\(", line)
        hostname = hostname_match.group(1).strip() if hostname_match else ""
        display_name = hostname if hostname and hostname != "?" else f"Wi-Fi Device {ip_address}"
        device_id = f"wifi-{mac_address.replace(':', '-')}"
        if device_id in seen_ids:
            continue

        seen_ids.add(device_id)
        devices.append(
            _make_device(
                device_id=device_id,
                name=display_name,
                imei=mac_address,
                connection_type="wifi",
            )
        )

    return devices


def _iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_dicts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_dicts(nested)


def _iter_bluetooth_connected_devices(payload: Any) -> Iterable[tuple[str, dict[str, Any]]]:
    if not isinstance(payload, dict):
        return

    entries = payload.get("SPBluetoothDataType", [])
    if not isinstance(entries, list):
        return

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        connected_devices = entry.get("device_connected", [])
        if not isinstance(connected_devices, list):
            continue

        for device_item in connected_devices:
            if not isinstance(device_item, dict) or len(device_item) != 1:
                continue

            [(device_name, device_details)] = device_item.items()
            if isinstance(device_details, dict):
                yield device_name, device_details


def discover_bluetooth_devices() -> List[Device]:
    """Discover paired or connected Bluetooth devices on macOS."""
    if platform.system() != "Darwin":
        return []

    result = _run_command(["system_profiler", "SPBluetoothDataType", "-json"], timeout=8)
    if not result or result.returncode != 0:
        return []

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    devices: List[Device] = []
    seen_ids: set[str] = set()

    for name, item in _iter_bluetooth_connected_devices(payload):
        name = str(name or item.get("device_name") or item.get("_name") or item.get("name") or "").strip()
        if not name:
            continue

        address = str(
            item.get("device_address")
            or item.get("bd_addr")
            or item.get("address")
            or item.get("device_id")
            or name
        ).strip()
        if not address:
            continue

        device_id = f"bluetooth-{re.sub(r'[^a-z0-9]+', '-', address.lower()).strip('-')}"
        if device_id in seen_ids:
            continue

        seen_ids.add(device_id)
        devices.append(
            _make_device(
                device_id=device_id,
                name=name,
                imei=address,
                connection_type="bluetooth",
                battery_display="No battery input",
            )
        )

    return devices
