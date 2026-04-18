#!/usr/bin/env python3
"""ReST Performance Bed – WiFi Setup Utility.

Replicates the setup flow of the official Android app so that beds can be
(re)configured without it.  Connect your computer to the pump's hotspot
(SSID: ReST-<mac_suffix>, default gateway 10.0.0.1) then run this tool.

Supported workflows
───────────────────
  setup   – Full first-time setup: scan → pick network → send creds → go indirect
  wifi    – Change WiFi credentials on a pump already on your network
  status  – Show device info, WiFi state, firmware, cloud, temps
  scan    – List WiFi networks visible to the pump
  direct  – Switch pump into AP / hotspot mode
  indirect – Switch pump into WiFi client mode
  dump    – Dump the full /api response as JSON

Usage
─────
  # Interactive setup via AP hotspot (default pump IP 10.0.0.1)
  python rest_bed_setup.py setup

  # Setup with explicit pump IP
  python rest_bed_setup.py setup --host 10.0.0.1

  # Change WiFi on a pump already on your LAN
  python rest_bed_setup.py wifi --host 10.0.17.182 --ssid MyNetwork --password secret

  # Quick status check
  python rest_bed_setup.py status --host 10.0.17.182

  # Dump full API state
  python rest_bed_setup.py dump --host 10.0.17.182
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_AP_HOST = "10.0.0.1"
TIMEOUT = 10


# ── HTTP helpers ────────────────────────────────────────────────────

def _url(host: str, path: str) -> str:
    return f"http://{host}{path}"


def _get(host: str, path: str) -> Any:
    req = urllib.request.Request(_url(host, path))
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def _put(host: str, path: str, body: Any) -> int:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        _url(host, path),
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status


def _reachable(host: str) -> bool:
    try:
        _get(host, "/api/device")
        return True
    except Exception:
        return False


# ── Display helpers ─────────────────────────────────────────────────

def _print_device(data: dict) -> None:
    print(f"  Name:     {data.get('name', '?')}")
    print(f"  Class:    {data.get('class', '?')}")
    print(f"  ID:       {data.get('id', '?')}")
    print(f"  Address:  {data.get('address', '?')}")
    print(f"  Model:    {data.get('model', '?')}")
    print(f"  Config:   {data.get('configuration', '?')}")


def _print_wifi(data: dict) -> None:
    print(f"  SSID:     {data.get('ssid', '?')}")
    print(f"  Mode:     {data.get('mode', '?')}")
    networks = data.get("list", [])
    if networks:
        print(f"  Visible networks ({len(networks)}):")
        for i, ssid in enumerate(networks, 1):
            print(f"    {i:2d}. {ssid}")


# ── Commands ────────────────────────────────────────────────────────

def cmd_status(host: str) -> None:
    """Show device info, WiFi state, firmware, cloud, and temperatures."""
    print(f"\n── Connecting to {host} ──")
    try:
        full = _get(host, "/api")
    except Exception as exc:
        print(f"  ERROR: Cannot reach pump at {host}: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n[Device]")
    _print_device(full.get("device", {}))

    print("\n[WiFi]")
    _print_wifi(full.get("wifi", {}))

    fw = full.get("firmware", {})
    print(f"\n[Firmware]")
    print(f"  Version:  {fw.get('version', '?')}")

    cloud = full.get("cloud", {})
    print(f"\n[Cloud]")
    print(f"  Enabled:   {cloud.get('enabled', '?')}")
    print(f"  Connected: {cloud.get('connected', '?')}")

    temp = full.get("temperature", {})
    print(f"\n[Temperature]")
    print(f"  CPU:       {temp.get('cpu', '?')}°C (max {temp.get('cpumax', '?')}°C)")
    print(f"  Enclosure: {temp.get('enclosure', '?')}°C (max {temp.get('enclosuremax', '?')}°C)")
    print(f"  Overheated:{temp.get('overheated', '?')}")

    print(f"\n[Time]")
    print(f"  Pump time: {full.get('time', '?')}")
    print()


def cmd_scan(host: str) -> list[str]:
    """List WiFi networks visible to the pump."""
    print(f"\n── Scanning for WiFi networks via {host} ──")
    try:
        networks = _get(host, "/api/wifi/list")
    except Exception as exc:
        print(f"  ERROR: Cannot reach pump: {exc}", file=sys.stderr)
        sys.exit(1)

    if not networks:
        print("  No networks found.")
        return []

    print(f"  Found {len(networks)} network(s):\n")
    for i, ssid in enumerate(networks, 1):
        print(f"    {i:2d}. {ssid}")
    print()
    return networks


def cmd_wifi(host: str, ssid: str, password: str, *, switch_indirect: bool = True) -> None:
    """Set WiFi credentials on the pump.  Optionally switch to indirect mode."""
    print(f"\n── Setting WiFi on {host} ──")
    print(f"  Target SSID: {ssid}")

    # Verify reachable first
    if not _reachable(host):
        print(f"  ERROR: Cannot reach pump at {host}", file=sys.stderr)
        sys.exit(1)

    # Get current state
    try:
        current = _get(host, "/api/wifi")
        print(f"  Current SSID: {current.get('ssid', '?')}")
        print(f"  Current mode: {current.get('mode', '?')}")
    except Exception:
        pass

    # Send credentials
    print(f"\n  Sending WiFi credentials...")
    try:
        status = _put(host, "/api/wifi", {"ssid": ssid, "password": password})
        print(f"  PUT /api/wifi → HTTP {status}")
    except urllib.error.URLError as exc:
        # The pump may drop the connection as it reconnects
        print(f"  PUT /api/wifi → connection dropped (expected during WiFi switch)")

    # If in direct (AP) mode, switch to indirect (client) mode
    if switch_indirect:
        try:
            current_mode = _get(host, "/api/wifi/mode")
            if current_mode == "direct":
                print(f"  Switching from direct (AP) to indirect (client) mode...")
                _put(host, "/api/wifi/mode", "indirect")
                print(f"  PUT /api/wifi/mode → sent 'indirect'")
                print(f"\n  ⚠  Pump will disconnect from AP and join '{ssid}'.")
                print(f"     Connect your computer back to your regular network.")
                print(f"     The pump should appear on the network within 30 seconds.")
            else:
                print(f"  Already in indirect mode – pump will reconnect to '{ssid}'.")
        except Exception:
            # May have already disconnected after wifi creds were set
            print(f"  Could not check/set mode (pump may have already switched).")

    print(f"\n  Done.\n")


def cmd_setup(host: str) -> None:
    """Interactive first-time setup flow (run while connected to pump's AP)."""
    print(f"""
╔══════════════════════════════════════════════════════════╗
║         ReST Performance Bed – WiFi Setup               ║
╠══════════════════════════════════════════════════════════╣
║  1. Connect to the pump's WiFi hotspot                  ║
║     (SSID looks like: ReST-XXXXXX)                      ║
║  2. The pump's IP is usually {DEFAULT_AP_HOST:<26s}║
║  3. This tool will scan for networks and configure WiFi ║
╚══════════════════════════════════════════════════════════╝
""")

    print(f"── Checking connection to pump at {host} ──")
    if not _reachable(host):
        print(f"  ERROR: Cannot reach pump at {host}")
        print(f"  Make sure you are connected to the pump's WiFi hotspot.")
        print(f"  The SSID looks like 'ReST-XXXXXX' and the pump IP is {DEFAULT_AP_HOST}")
        sys.exit(1)

    # Show device info
    try:
        device = _get(host, "/api/device")
        print(f"\n  Connected to pump!")
        _print_device(device)
    except Exception as exc:
        print(f"  WARNING: Could not get device info: {exc}")

    # Check current WiFi state
    try:
        wifi = _get(host, "/api/wifi")
        current_mode = wifi.get("mode", "?")
        current_ssid = wifi.get("ssid", "")
        print(f"\n  Current WiFi mode: {current_mode}")
        if current_ssid:
            print(f"  Current SSID:      {current_ssid}")
    except Exception:
        current_mode = "direct"

    # Scan for networks
    print(f"\n── Scanning for available WiFi networks ──\n")
    try:
        networks = _get(host, "/api/wifi/list")
    except Exception:
        networks = []

    if not networks:
        print("  No networks found. You can enter an SSID manually.\n")

    for i, ssid in enumerate(networks, 1):
        print(f"    {i:2d}. {ssid}")

    # Let user pick or type SSID
    print()
    choice = input("  Enter network number or type SSID: ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(networks):
            ssid = networks[idx]
        else:
            print("  Invalid selection.")
            sys.exit(1)
    else:
        ssid = choice

    if not ssid:
        print("  No SSID provided.")
        sys.exit(1)

    # Get password
    password = input(f"  Enter password for '{ssid}': ").strip()

    # Confirm
    print(f"\n  Will configure pump to join:")
    print(f"    SSID:     {ssid}")
    print(f"    Password: {'*' * len(password)}")
    confirm = input(f"\n  Proceed? [Y/n] ").strip().lower()
    if confirm and confirm != "y":
        print("  Aborted.")
        sys.exit(0)

    # Step 1: Send WiFi credentials
    print(f"\n── Step 1: Sending WiFi credentials ──")
    try:
        status = _put(host, "/api/wifi", {"ssid": ssid, "password": password})
        print(f"  PUT /api/wifi → HTTP {status}")
    except urllib.error.URLError:
        print(f"  PUT /api/wifi → connection dropped (may be expected)")

    # Step 2: Switch to indirect (client) mode if currently in direct (AP) mode
    if current_mode == "direct":
        print(f"\n── Step 2: Switching to client mode ──")
        try:
            _put(host, "/api/wifi/mode", "indirect")
            print(f"  PUT /api/wifi/mode → sent 'indirect'")
        except urllib.error.URLError:
            print(f"  PUT /api/wifi/mode → connection dropped (expected)")

    print(f"""
╔══════════════════════════════════════════════════════════╗
║  Setup complete!                                        ║
╠══════════════════════════════════════════════════════════╣
║  The pump should now join '{ssid[:30]}'
║                                                         ║
║  Next steps:                                            ║
║  1. Disconnect from the pump's hotspot                  ║
║  2. Reconnect to your regular WiFi network              ║
║  3. The pump should appear on the network in ~30sec     ║
║  4. Check your router/DHCP for the pump's new IP        ║
║  5. Run: python rest_bed_setup.py status --host <IP>    ║
╚══════════════════════════════════════════════════════════╝
""")


def cmd_direct(host: str) -> None:
    """Switch pump to AP / hotspot mode."""
    print(f"\n── Switching {host} to direct (AP) mode ──")
    try:
        _put(host, "/api/wifi/mode", "direct")
        print(f"  PUT /api/wifi/mode → sent 'direct'")
        print(f"  Pump will start broadcasting its hotspot (ReST-XXXXXX).")
        print(f"  WARNING: Pump will disconnect from current WiFi network.\n")
    except Exception as exc:
        print(f"  ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_indirect(host: str) -> None:
    """Switch pump to WiFi client mode."""
    print(f"\n── Switching {host} to indirect (client) mode ──")
    try:
        _put(host, "/api/wifi/mode", "indirect")
        print(f"  PUT /api/wifi/mode → sent 'indirect'")
        print(f"  Pump will join its configured WiFi network.\n")
    except Exception as exc:
        print(f"  ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_dump(host: str) -> None:
    """Dump the full /api response as formatted JSON."""
    try:
        data = _get(host, "/api")
        print(json.dumps(data, indent=2))
    except Exception as exc:
        print(f"ERROR: Cannot reach pump at {host}: {exc}", file=sys.stderr)
        sys.exit(1)


# ── CLI ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="rest_bed_setup",
        description="ReST Performance Bed – WiFi Setup Utility",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # setup
    p_setup = sub.add_parser("setup", help="Interactive first-time WiFi setup (connect to pump AP first)")
    p_setup.add_argument("--host", default=DEFAULT_AP_HOST, help=f"Pump IP (default: {DEFAULT_AP_HOST})")

    # wifi
    p_wifi = sub.add_parser("wifi", help="Set WiFi credentials on a reachable pump")
    p_wifi.add_argument("--host", required=True, help="Pump IP address or hostname")
    p_wifi.add_argument("--ssid", required=True, help="WiFi network name")
    p_wifi.add_argument("--password", required=True, help="WiFi password")
    p_wifi.add_argument("--no-switch", action="store_true", help="Don't switch to indirect mode after setting creds")

    # status
    p_status = sub.add_parser("status", help="Show device status")
    p_status.add_argument("--host", required=True, help="Pump IP address or hostname")

    # scan
    p_scan = sub.add_parser("scan", help="List WiFi networks visible to the pump")
    p_scan.add_argument("--host", required=True, help="Pump IP address or hostname")

    # direct
    p_direct = sub.add_parser("direct", help="Switch pump to AP / hotspot mode")
    p_direct.add_argument("--host", required=True, help="Pump IP address or hostname")

    # indirect
    p_indirect = sub.add_parser("indirect", help="Switch pump to WiFi client mode")
    p_indirect.add_argument("--host", required=True, help="Pump IP address or hostname")

    # dump
    p_dump = sub.add_parser("dump", help="Dump full API state as JSON")
    p_dump.add_argument("--host", required=True, help="Pump IP address or hostname")

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup(args.host)
    elif args.command == "wifi":
        cmd_wifi(args.host, args.ssid, args.password, switch_indirect=not args.no_switch)
    elif args.command == "status":
        cmd_status(args.host)
    elif args.command == "scan":
        cmd_scan(args.host)
    elif args.command == "direct":
        cmd_direct(args.host)
    elif args.command == "indirect":
        cmd_indirect(args.host)
    elif args.command == "dump":
        cmd_dump(args.host)


if __name__ == "__main__":
    main()
