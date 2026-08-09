#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "urllib3",
# ]
# ///
#
# homenet - Omada ER605 router CLI
# Copyright (C) 2026  Rafael Jeffman
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""Access an Omada ER605 router and list WAN networks."""

import argparse
import getpass
import json
import sys

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_HOST = "http://172.17.2.1"
REFERER_PATH = "/webpages/login.html"


def rsa_encrypt(plaintext, n_hex, e_hex):
    """RSA encrypt with no padding, matching the TP-Link JS implementation."""
    n = int(n_hex, 16)
    e = int(e_hex, 16)
    key_len = (n.bit_length() + 7) >> 3

    ba = bytearray()
    for ch in plaintext:
        code = ord(ch)
        if code < 128:
            ba.append(code)
        elif code < 2048:
            ba.append((code & 63) | 128)
            ba.append((code >> 6) | 192)
        else:
            ba.append((code & 63) | 128)
            ba.append(((code >> 6) & 63) | 128)
            ba.append((code >> 12) | 224)

    ba.extend(b"\x00" * (key_len - len(ba)))

    m = int.from_bytes(ba, byteorder="big")
    c = pow(m, e, n)
    result = format(c, "x")
    return result.zfill(256)


class OmadaRouter:
    def __init__(self, host):
        self.host = host.rstrip("/")
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers["Referer"] = f"{self.host}{REFERER_PATH}"
        self.stok = ""

    def _url(self, path):
        return f"{self.host}/cgi-bin/luci/;stok={self.stok}{path}"

    def _post(self, path, payload):
        url = self._url(path)
        resp = self.session.post(
            url, data={"data": json.dumps(payload)}, timeout=10
        )
        resp.raise_for_status()
        return resp.json()

    def _get_auth_keys(self):
        login_data = self._post(
            "/login?form=login", {"method": "get"}
        )
        result = login_data.get("result", {})
        password_keys = result.get("password", [])
        if len(password_keys) < 2:
            raise RuntimeError("Failed to get RSA keys from router")

        locale_resp = self.session.post(
            self._url("/locale?form=lang"),
            data={"operation": "read"},
            timeout=10,
        )
        locale_data = locale_resp.json()
        uptime = locale_data.get("result", {}).get("uptime", "0")

        return password_keys[0], password_keys[1], str(uptime)

    def login(self, username, password):
        n_hex, e_hex, uptime = self._get_auth_keys()
        encrypted = rsa_encrypt(f"{password}_{uptime}", n_hex, e_hex)

        data = self._post(
            "/login?form=login",
            {
                "method": "login",
                "params": {"username": username, "password": encrypted},
            },
        )
        error = data.get("error_code")
        if str(error) != "0":
            error_map = {
                "700": "Invalid username or password",
                "701": "Too many login attempts, try again later",
                "702": "User conflict -- another session is active",
            }
            msg = error_map.get(
                str(error), f"Login failed (error {error})"
            )
            raise RuntimeError(msg)

        self.stok = data.get("result", {}).get("stok", data.get("stok", ""))
        if not self.stok:
            raise RuntimeError(
                "Login succeeded but no session token returned"
            )

    def logout(self):
        if self.stok:
            try:
                self._post(
                    "/admin/system?form=logout", {"method": "set"}
                )
            except Exception:
                pass
            self.stok = ""

    def get_interface_status(self):
        return self._post(
            "/admin/interface?form=status3", {"method": "get"}
        )

    def get_wan_interfaces(self):
        data = self.get_interface_status()
        if str(data.get("error_code", -1)) != "0":
            raise RuntimeError(
                f"Failed to get interface status "
                f"(error {data.get('error_code')})"
            )
        result = data.get("result", {})
        interfaces = result.get("normal", [])
        return [
            iface
            for iface in interfaces
            if iface.get("t_name", "").startswith("WAN")
        ]

    def get_dhcp_clients(self):
        data = self._post(
            "/admin/dhcps?form=client", {"method": "get"}
        )
        if str(data.get("error_code", -1)) != "0":
            raise RuntimeError(
                f"Failed to get DHCP clients "
                f"(error {data.get('error_code')})"
            )
        return data.get("result", [])

    def get_dhcp_reservations(self):
        data = self._post(
            "/admin/dhcps?form=reservation", {"method": "get"}
        )
        if str(data.get("error_code", -1)) != "0":
            raise RuntimeError(
                f"Failed to get DHCP reservations "
                f"(error {data.get('error_code')})"
            )
        return data.get("result", [])

    def add_dhcp_reservation(self, record):
        data = self._post("/admin/dhcps?form=reservation", {
            "method": "add",
            "params": {
                "index": 0,
                "old": "add",
                "new": record,
                "ip": "add",
            },
        })
        if str(data.get("error_code", -1)) != "0":
            raise RuntimeError(
                f"Failed to add DHCP reservation "
                f"(error {data.get('error_code')})"
            )
        return data

    def update_dhcp_reservation(
        self, index, old_record, new_record, original_ip
    ):
        old_without_ip = {
            k: v for k, v in old_record.items() if k != "ip"
        }
        data = self._post("/admin/dhcps?form=reservation", {
            "method": "set",
            "params": {
                "index": index,
                "old": old_without_ip,
                "new": new_record,
                "ip": original_ip,
            },
        })
        if str(data.get("error_code", -1)) != "0":
            raise RuntimeError(
                f"Failed to update DHCP reservation "
                f"(error {data.get('error_code')})"
            )
        return data

    def delete_dhcp_reservation(self, ip, index, interface):
        data = self._post("/admin/dhcps?form=reservation", {
            "method": "delete",
            "params": {
                "key": ip,
                "index": str(index),
                "extraKey": interface,
            },
        })
        if str(data.get("error_code", -1)) != "0":
            raise RuntimeError(
                f"Failed to delete DHCP reservation "
                f"(error {data.get('error_code')})"
            )
        return data


# -- wan command -----------------------------------------------------


def _print_single_wan(wan):
    name = wan.get("t_name", "?")
    label = wan.get("t_label", "")
    secondary = wan.get("second_conn", False)

    header = name
    if label:
        header += f" ({label})"
    if secondary:
        header += " [secondary]"

    print(f"\n{'=' * 50}")
    print(f"  {header}")
    print(f"{'=' * 50}")

    fields = [
        ("Status", "t_isup"),
        ("Protocol", "t_proto"),
        ("Link Type", "t_linktype"),
        ("IP Address", "ipaddr"),
        ("Netmask", "netmask"),
        ("Gateway", "gateway"),
        ("Primary DNS", "dns1"),
        ("Secondary DNS", "dns2"),
        ("MAC Address", "macaddr"),
    ]

    for display_name, key in fields:
        if key not in wan:
            continue
        value = wan[key]
        if key == "t_isup":
            value = "Up" if value else "Down"
        print(f"  {display_name:<20s} {value}")

    known = {f[1] for f in fields} | {
        "t_name", "t_label", "t_type", "second_conn", "error_code",
    }
    for key, value in wan.items():
        if key not in known:
            print(f"  {key:<20s} {value}")


def cmd_wan(router, args):
    wan_list = router.get_wan_interfaces()
    if args.output_json:
        print(json.dumps(wan_list, indent=2))
        return
    if not wan_list:
        print("No WAN interfaces found.")
        return
    for wan in wan_list:
        _print_single_wan(wan)


# -- dhcp assigned command -------------------------------------------


def cmd_dhcp_assigned(router, args):
    clients = router.get_dhcp_clients()
    if args.lan:
        lan_filter = args.lan.lower()
        clients = [
            c for c in clients
            if c.get("interface", "").lower() == lan_filter
        ]

    if args.output_json:
        print(json.dumps(clients, indent=2))
        return

    if not clients:
        print("No DHCP clients found.")
        return

    hdr = (
        f"  {'Name':<24s} {'IP Address':<18s} "
        f"{'MAC Address':<20s} {'Lease':<12s} {'Interface'}"
    )
    print()
    print(hdr)
    print(f"  {'-' * (len(hdr) - 2)}")
    for c in clients:
        name = c.get("name", "")
        ip = c.get("ipaddr", "")
        mac = c.get("macaddr", "")
        lease = c.get("leasetime", "")
        iface = c.get("interface", "")
        if c.get("bind") == "1":
            lease = "Static"
        print(f"  {name:<24s} {ip:<18s} {mac:<20s} {lease:<12s} {iface}")


# -- dhcp reserved command -------------------------------------------


def cmd_dhcp_reserved(router, args):
    reservations = router.get_dhcp_reservations()
    if args.lan:
        lan_filter = args.lan.lower()
        reservations = [
            r for r in reservations
            if r.get("interface", "").lower() == lan_filter
        ]

    if args.output_json:
        print(json.dumps(reservations, indent=2))
        return

    if not reservations:
        print("No DHCP reservations found.")
        return

    hdr = (
        f"  {'Description':<36s} {'IP Address':<18s} "
        f"{'MAC Address':<20s} {'Status':<10s} {'Interface'}"
    )
    print()
    print(hdr)
    print(f"  {'-' * (len(hdr) - 2)}")
    for r in reservations:
        note = r.get("note", "")
        ip = r.get("ip", "")
        mac = r.get("mac", "")
        enabled = "Enabled" if r.get("enable") == "on" else "Disabled"
        iface = r.get("interface", "")
        print(
            f"  {note:<36s} {ip:<18s} {mac:<20s} {enabled:<10s} {iface}"
        )


# -- dhcp reserve command --------------------------------------------


def _normalize_mac(mac):
    return mac.replace(":", "-").upper()


def cmd_dhcp_reserve(router, args):
    ip = args.ip
    mac = _normalize_mac(args.mac) if args.mac else None
    name = args.name
    lan = args.lan
    enable = "on"
    if args.disable:
        enable = "off"
    bind = "1"
    if args.no_bind:
        bind = "0"

    reservations = router.get_dhcp_reservations()
    existing = None
    existing_index = None
    for i, r in enumerate(reservations):
        if r.get("ip") == ip:
            existing = r
            existing_index = i
            break

    if existing:
        new_record = {
            "mac": mac if mac else existing["mac"],
            "ip": ip,
            "note": name if name is not None else existing.get("note", ""),
            "enable": enable,
            "interface": lan if lan else existing.get("interface", "LAN"),
            "bind": bind,
        }
        router.update_dhcp_reservation(
            existing_index, existing, new_record, ip
        )
        print(f"Updated reservation for {ip}")
    else:
        if not mac:
            print(
                "Error: --mac is required when creating a new reservation",
                file=sys.stderr,
            )
            sys.exit(1)
        new_record = {
            "mac": mac,
            "ip": ip,
            "note": name or "",
            "enable": enable,
            "interface": lan or "LAN",
            "bind": bind,
        }
        router.add_dhcp_reservation(new_record)
        print(f"Added reservation for {ip}")


# -- dhcp unreserve command ------------------------------------------


def cmd_dhcp_unreserve(router, args):
    ip = args.ip
    reservations = router.get_dhcp_reservations()
    for i, r in enumerate(reservations):
        if r.get("ip") == ip:
            router.delete_dhcp_reservation(
                ip, i, r.get("interface", "LAN")
            )
            print(f"Deleted reservation for {ip}")
            return

    print(f"Error: No reservation found for {ip}", file=sys.stderr)
    sys.exit(1)


# -- CLI -------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        description="Omada ER605 router CLI"
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Router URL (default: {DEFAULT_HOST})",
    )
    parser.add_argument("--user", "-u", default="admin", help="Username")
    parser.add_argument(
        "--password", "-p", help="Password (prompted if omitted)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output raw JSON",
    )

    subparsers = parser.add_subparsers(dest="command")

    # wan
    wan_parser = subparsers.add_parser(
        "wan", help="List WAN interfaces"
    )
    wan_parser.set_defaults(func=cmd_wan)

    # dhcp
    dhcp_parser = subparsers.add_parser(
        "dhcp", help="DHCP operations"
    )
    dhcp_sub = dhcp_parser.add_subparsers(dest="dhcp_command")

    # dhcp assigned
    assigned_parser = dhcp_sub.add_parser(
        "assigned", help="List DHCP-assigned hosts"
    )
    assigned_parser.add_argument(
        "--lan",
        default=None,
        help="Filter by LAN interface name (e.g. 'lan')",
    )
    assigned_parser.set_defaults(func=cmd_dhcp_assigned)

    # dhcp reserved
    reserved_parser = dhcp_sub.add_parser(
        "reserved", help="List DHCP address reservations"
    )
    reserved_parser.add_argument(
        "--lan",
        default=None,
        help="Filter by LAN interface name (e.g. 'LAN1')",
    )
    reserved_parser.set_defaults(func=cmd_dhcp_reserved)

    # dhcp reserve
    reserve_parser = dhcp_sub.add_parser(
        "reserve",
        help="Add or modify a DHCP address reservation",
    )
    reserve_parser.add_argument(
        "--ip", required=True, help="IP address to reserve"
    )
    reserve_parser.add_argument(
        "--mac",
        default=None,
        help="MAC address (required for new, optional for modify)",
    )
    reserve_parser.add_argument(
        "--name", default=None, help="Description / note"
    )
    reserve_parser.add_argument(
        "--lan",
        default=None,
        help="LAN interface (default: LAN for new reservations)",
    )
    reserve_parser.add_argument(
        "--disable",
        action="store_true",
        default=False,
        help="Create reservation as disabled",
    )
    reserve_parser.add_argument(
        "--no-bind",
        action="store_true",
        default=False,
        help="Do not export to IP-MAC binding",
    )
    reserve_parser.set_defaults(func=cmd_dhcp_reserve)

    # dhcp unreserve
    unreserve_parser = dhcp_sub.add_parser(
        "unreserve",
        help="Remove a DHCP address reservation",
    )
    unreserve_parser.add_argument(
        "--ip", required=True, help="IP address to remove"
    )
    unreserve_parser.set_defaults(func=cmd_dhcp_unreserve)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    password = args.password or getpass.getpass(
        f"Password for {args.user}@{args.host}: "
    )

    router = OmadaRouter(args.host)
    try:
        router.login(args.user, password)
        print(f"Connected to {args.host}")
        args.func(router, args)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(
            f"Error: Cannot connect to {args.host}", file=sys.stderr
        )
        sys.exit(1)
    finally:
        router.logout()


if __name__ == "__main__":
    main()
