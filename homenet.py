#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "keyring",
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
import configparser
import getpass
import ipaddress
import json
import os
import re
import sys

import keyring
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REFERER_PATH = "/webpages/login.html"
CONFIG_SEARCH_PATHS = [
    os.path.expanduser("~/.config/homenet/config"),
    "./.homenet",
]


def _read_config_file(cfg, path):
    """Read a config file, tolerating missing section headers."""
    try:
        cfg.read(path)
    except configparser.MissingSectionHeaderError:
        with open(path) as fh:
            cfg.read_string("[DEFAULT]\n" + fh.read(), source=path)


def load_config(config_path=None):
    """Load configuration from file.

    Search order: --config path, ~/.config/homenet/config, ./.homenet
    """
    cfg = configparser.ConfigParser()
    if config_path:
        if not os.path.isfile(config_path):
            print(
                f"Error: Config file not found: {config_path}",
                file=sys.stderr,
            )
            sys.exit(1)
        _read_config_file(cfg, config_path)
    else:
        for path in CONFIG_SEARCH_PATHS:
            if os.path.isfile(path):
                _read_config_file(cfg, path)
    return cfg


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
            except (requests.RequestException, RuntimeError):
                pass
            self.stok = ""

    def _post_diag(self, payload):
        url = self._url("/admin/diagnostic?form=diag")
        resp = self.session.post(
            url, data={"data": json.dumps(payload)}, timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    def ping(self, target, iface, count=3):
        import time

        params = {
            "type": "0",
            "ipaddr": target,
            "iface": iface,
            "count": str(count),
            "pktsize": "64",
        }
        self._post_diag({"method": "start", "params": params})
        for _ in range(count + 10):
            time.sleep(1)
            data = self._post_diag(
                {"method": "continue", "params": params}
            )
            result = data.get("result", {})
            if str(result.get("finish")) == "1":
                return result.get("my_result", "")
        return None

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

    def get_wan_bandwidth(self):
        """Fetch configured bandwidth for each WAN port.

        Returns a dict mapping WAN name to {uplink, downlink} in Kbps.
        """
        mode = self._post(
            "/admin/interface_wan?form=wanmode", {"method": "get"}
        )
        mode_result = mode.get("result", {})
        wan_numbers = mode_result.get("wan_numbers", [])
        wan_names = mode_result.get("wan_names", [])

        num_to_label = {}
        for entry in wan_names:
            num_to_label[entry.get("index")] = entry.get("name", "")

        result = {}
        for num in wan_numbers:
            cfg = self._post(
                "/admin/interface_wan?form=wanconfig",
                {"method": "get", "params": {"wan_id": num}},
            )
            cfg_result = cfg.get("result", {})
            label = num_to_label.get(num, f"WAN{num}")
            result[label] = {
                "uplink": cfg_result.get("uplink", 0),
                "downlink": cfg_result.get("downlink", 0),
            }
        return result

    def get_interface_stats(self):
        data = self._post(
            "/admin/ifstat?form=list", {"method": "get"}
        )
        if str(data.get("error_code", -1)) != "0":
            raise RuntimeError(
                f"Failed to get interface stats "
                f"(error {data.get('error_code')})"
            )
        return {s["zone"]: s for s in data.get("result", [])}

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


def _format_kbps(kbps):
    kbps = int(kbps)
    if kbps >= 1000:
        return f"{kbps / 1000:.0f} Mbps"
    return f"{kbps} Kbps"


def _print_single_wan(wan, bandwidth=None):
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

    if bandwidth:
        up = bandwidth.get("uplink", 0)
        down = bandwidth.get("downlink", 0)
        if up:
            print(f"  {'Upstream':<20s} {_format_kbps(up)}")
        if down:
            print(f"  {'Downstream':<20s} {_format_kbps(down)}")

    known = {f[1] for f in fields} | {
        "t_name", "t_label", "t_type", "second_conn", "error_code",
    }
    for key, value in wan.items():
        if key not in known:
            print(f"  {key:<20s} {value}")


def cmd_wan(router, args):
    wan_list = [
        w for w in router.get_wan_interfaces()
        if w.get("t_proto") != "none"
    ]
    if not wan_list:
        print("No WAN interfaces found.")
        return
    bandwidth = router.get_wan_bandwidth()
    if args.output_json:
        for w in wan_list:
            bw = bandwidth.get(w.get("t_label"), {})
            if bw:
                w["bandwidth"] = bw
        print(json.dumps(wan_list, indent=2))
        return
    for wan in wan_list:
        _print_single_wan(wan, bandwidth.get(wan.get("t_label")))


def _format_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def cmd_wan_stats(router, args):
    wan_list = [
        w for w in router.get_wan_interfaces()
        if w.get("t_proto") != "none"
    ]
    if not wan_list:
        print("No WAN interfaces found.")
        return

    stats = router.get_interface_stats()
    bandwidth = router.get_wan_bandwidth()

    if args.output_json:
        result = []
        for w in wan_list:
            name = w.get("t_name", "?")
            s = dict(stats.get(name, {}))
            s["interface"] = name
            s["label"] = w.get("t_label", "")
            bw = bandwidth.get(w.get("t_label"), {})
            if bw:
                s["bandwidth"] = bw
            result.append(s)
        print(json.dumps(result, indent=2))
        return

    for w in wan_list:
        name = w.get("t_name", "?")
        label = w.get("t_label", "")
        header = f"{name} ({label})" if label else name
        s = stats.get(name, {})
        bw = bandwidth.get(label, {})

        print(f"\n{'=' * 50}")
        print(f"  {header}")
        print(f"{'=' * 50}")
        if bw.get("downlink"):
            print(f"  {'Downstream':<20s} {_format_kbps(bw['downlink'])}")
        if bw.get("uplink"):
            print(f"  {'Upstream':<20s} {_format_kbps(bw['uplink'])}")
        print(f"  {'RX Rate':<20s} {s.get('rx_bps', 0)} KB/s")
        print(f"  {'TX Rate':<20s} {s.get('tx_bps', 0)} KB/s")
        print(f"  {'RX Packets/s':<20s} {s.get('rx_pps', 0)}")
        print(f"  {'TX Packets/s':<20s} {s.get('tx_pps', 0)}")
        print(f"  {'Total RX':<20s} {_format_bytes(int(s.get('rx_bytes', 0)))}")
        print(f"  {'Total TX':<20s} {_format_bytes(int(s.get('tx_bytes', 0)))}")
        print(f"  {'Total RX Packets':<20s} {s.get('rx_pkts', 0)}")
        print(f"  {'Total TX Packets':<20s} {s.get('tx_pkts', 0)}")


DEFAULT_PING_TARGETS = ["8.8.8.8", "1.1.1.1"]


def cmd_wan_test(router, args):
    targets = [args.target] if args.target else DEFAULT_PING_TARGETS
    wan_list = router.get_wan_interfaces()
    primary_wans = [
        w for w in wan_list if not w.get("second_conn", False)
    ]
    if not primary_wans:
        print("No WAN interfaces found.")
        return

    results = []
    for wan in primary_wans:
        name = wan.get("t_name", "?")
        label = wan.get("t_label", "")
        header = f"{name} ({label})" if label else name

        passed = False
        output = ""
        for target in targets:
            print(f"  {header}: pinging {target}...", end="", flush=True)
            output = router.ping(target, name)
            if output and "bytes=" in output:
                passed = True
                print(" OK")
                break
            print(" FAIL")

        results.append({
            "interface": name,
            "label": label,
            "target": target,
            "passed": passed,
            "output": output or "",
        })

    if args.output_json:
        print(json.dumps(results, indent=2))
        return

    print()
    for r in results:
        label = r["label"]
        name = r["interface"]
        header = f"{name} ({label})" if label else name
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  {header:<20s} {status:<6s} ({r['target']})")


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


_MAC_RE = re.compile(
    r"^[0-9A-Fa-f]{2}([:-])[0-9A-Fa-f]{2}"
    r"(\1[0-9A-Fa-f]{2}){4}$"
)


def _validate_ip(value):
    try:
        ipaddress.ip_address(value)
    except ValueError:
        print(f"Error: Invalid IP address: {value}", file=sys.stderr)
        sys.exit(1)
    return value


def _validate_mac(value):
    if not _MAC_RE.match(value):
        print(
            f"Error: Invalid MAC address: {value} "
            f"(expected XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX)",
            file=sys.stderr,
        )
        sys.exit(1)
    return value.replace(":", "-").upper()


def cmd_dhcp_reserve(router, args):
    ip = _validate_ip(args.ip)
    mac = _validate_mac(args.mac) if args.mac else None
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
    ip = _validate_ip(args.ip)
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


# -- password commands -----------------------------------------------

KEYRING_SERVICE = "homenet"


def cmd_password_set(router, args):
    password = getpass.getpass(f"Password for {args.user}: ")
    keyring.set_password(KEYRING_SERVICE, args.user, password)
    print(f"Password stored in keyring for user '{args.user}'")


def cmd_password_clear(router, args):
    try:
        keyring.delete_password(KEYRING_SERVICE, args.user)
        print(f"Password removed from keyring for user '{args.user}'")
    except keyring.errors.PasswordDeleteError:
        print(
            f"No password found in keyring for user '{args.user}'",
            file=sys.stderr,
        )
        sys.exit(1)


# -- CLI -------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        description="Omada ER605 router CLI"
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to configuration file",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Router URL (overrides GATEWAY from config)",
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
        "wan", help="WAN operations"
    )
    wan_parser.set_defaults(func=cmd_wan)
    wan_sub = wan_parser.add_subparsers(dest="wan_command")

    # wan status
    wan_status_parser = wan_sub.add_parser(
        "status", help="List WAN interfaces"
    )
    wan_status_parser.set_defaults(func=cmd_wan)

    # wan test
    wan_test_parser = wan_sub.add_parser(
        "test", help="Test WAN connectivity by pinging a remote host"
    )
    wan_test_parser.add_argument(
        "--target", "-t",
        default=None,
        help="IP or hostname to ping (default: 8.8.8.8, fallback 1.1.1.1)",
    )
    wan_test_parser.set_defaults(func=cmd_wan_test)

    # wan stats
    wan_stats_parser = wan_sub.add_parser(
        "stats", help="Show live traffic statistics for WAN interfaces"
    )
    wan_stats_parser.set_defaults(func=cmd_wan_stats)

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

    # password
    password_parser = subparsers.add_parser(
        "password", help="Manage stored router password"
    )
    password_sub = password_parser.add_subparsers(
        dest="password_command"
    )

    # password set
    pw_set_parser = password_sub.add_parser(
        "set", help="Store the router password in the system keyring"
    )
    pw_set_parser.set_defaults(func=cmd_password_set, needs_login=False)

    # password clear
    pw_clear_parser = password_sub.add_parser(
        "clear",
        help="Remove the router password from the system keyring",
    )
    pw_clear_parser.set_defaults(
        func=cmd_password_clear, needs_login=False
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    if not getattr(args, "needs_login", True):
        args.func(None, args)
        return

    cfg = load_config(args.config)
    if not args.host:
        args.host = cfg.get("DEFAULT", "GATEWAY", fallback=None)
    if not args.host:
        print(
            "Error: No router host specified. "
            "Use --host or set GATEWAY in a config file.",
            file=sys.stderr,
        )
        sys.exit(1)

    password = args.password
    if not password:
        password = keyring.get_password(KEYRING_SERVICE, args.user)
    if not password:
        password = getpass.getpass(
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
