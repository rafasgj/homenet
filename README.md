# homenet

A command-line tool for managing a TP-Link Omada ER605 router. It communicates directly with the router's web API, allowing you to query network status and manage DHCP reservations without using the web interface.

## Installation

Requires Python 3.10 or later and:

- [keyring](https://pypi.org/project/keyring/) -- system keyring access (macOS Keychain, Linux SecretService)
- [requests](https://docs.python-requests.org/)
- [urllib3](https://urllib3.readthedocs.io/)

### Using uv

With [uv](https://docs.astral.sh/uv/) installed, the script can be run directly. Dependencies are resolved and cached automatically from the inline script metadata.

```
./homenet.py wan
```

### Using a virtual environment

```
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/homenet wan
```

## Configuration

The router address is read from a configuration file. The following paths are searched in order:

1. Path given by `--config` / `-c`
2. `~/.config/homenet/config`
3. `./.homenet`

The file uses INI format with a `GATEWAY` variable:

```ini
GATEWAY = http://172.17.2.1
```

## Password

The router password is resolved in this order:

1. `--password` / `-p` command-line option
2. System keyring (macOS Keychain, Linux SecretService / secret-tool)
3. Interactive prompt

Use the `password` command to manage the stored password:

```
homenet password set      # prompt and store password in keyring
homenet password clear    # remove password from keyring
```

The keyring entry is stored under the service name `homenet` with the login username (default `admin`). A different user can be specified with `-u`.

## Usage

```
homenet [-c CONFIG] [--host URL] [-u USER] [-p PASSWORD] [--json] <command>
```

Global options:

- `-c`, `--config` -- Path to a configuration file
- `--host` -- Router URL (overrides `GATEWAY` from config)
- `-u`, `--user` -- Login username (default: `admin`)
- `-p`, `--password` -- Login password; prompted interactively if omitted
- `--json` -- Output raw JSON instead of formatted tables

## Commands

### wan status

```
homenet wan status
```

Lists all WAN interfaces on the router, showing their status, protocol, IP address, gateway, DNS servers, and MAC address.

### wan test

```
homenet wan test [--target HOST]
```

Tests connectivity on each WAN port by pinging a remote host through the router. By default it pings `8.8.8.8` and falls back to `1.1.1.1` if the first fails. Use `--target` to specify a custom IP address or hostname. Shows progress during the test and prints a pass/fail summary for each interface.

### dhcp assigned

```
homenet dhcp assigned [--lan LAN]
```

Lists hosts that currently hold a DHCP lease. Each entry shows the hostname, IP address, MAC address, lease time, and interface. Use `--lan` to filter by a specific LAN interface.

### dhcp reserved

```
homenet dhcp reserved [--lan LAN]
```

Lists all static DHCP address reservations configured on the router. Use `--lan` to filter by interface.

### dhcp reserve

```
homenet dhcp reserve --ip IP [--mac MAC] [--name NOTE] [--lan LAN] [--disable] [--no-bind]
```

Creates a new DHCP reservation or modifies an existing one. If the given IP address already has a reservation, the command updates it with the provided values while preserving any fields that are not specified. If the IP address is not yet reserved, a new entry is created and `--mac` is required.

- `--name` sets a description for the reservation.
- `--lan` sets the LAN interface (defaults to `LAN` for new entries).
- `--disable` creates the reservation in a disabled state.
- `--no-bind` skips exporting the entry to the IP-MAC binding table.

MAC addresses can use either `:` or `-` as separators.

### dhcp unreserve

```
homenet dhcp unreserve --ip IP
```

Removes an existing DHCP reservation by IP address. Reports an error if no reservation exists for the given address.

## License

This project is licensed under the GNU General Public License v3.0 or later. See the [COPYING](COPYING) file for the full license text.
