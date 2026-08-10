"""Step definitions for DHCP commands."""

import argparse

from behave import given, when

from homenet import (
    cmd_dhcp_assigned,
    cmd_dhcp_reserve,
    cmd_dhcp_reserved,
    cmd_dhcp_unreserve,
)
from tests.environment import run_command

DHCP_CLIENTS = {
    "error_code": "0",
    "result": [
        {
            "name": "desktop-pc",
            "ipaddr": "192.168.0.100",
            "macaddr": "AA-BB-CC-DD-EE-01",
            "leasetime": "86400",
            "interface": "LAN",
            "bind": "0",
        },
        {
            "name": "laptop",
            "ipaddr": "192.168.0.101",
            "macaddr": "AA-BB-CC-DD-EE-02",
            "leasetime": "86400",
            "interface": "LAN",
            "bind": "0",
        },
    ],
}

DHCP_RESERVATIONS = {
    "error_code": "0",
    "result": [
        {
            "ip": "192.168.0.10",
            "mac": "AA-BB-CC-DD-EE-10",
            "note": "server",
            "enable": "on",
            "interface": "LAN",
            "bind": "1",
        },
    ],
}

EMPTY_RESULT = {"error_code": "0", "result": []}


@given("a router with DHCP clients")
def step_router_with_clients(context):
    context.mock_api.register("/admin/dhcps?form=client", "get", DHCP_CLIENTS)


@given("a router with no DHCP clients")
def step_router_no_clients(context):
    context.mock_api.register("/admin/dhcps?form=client", "get", EMPTY_RESULT)


@given("a router with DHCP reservations")
def step_router_with_reservations(context):
    context.mock_api.register(
        "/admin/dhcps?form=reservation", "get", DHCP_RESERVATIONS
    )
    context.mock_api.register(
        "/admin/dhcps?form=reservation",
        "set",
        {"error_code": "0", "result": {}},
    )
    context.mock_api.register(
        "/admin/dhcps?form=reservation",
        "delete",
        {"error_code": "0", "result": {}},
    )


@given("a router with no DHCP reservations")
def step_router_no_reservations(context):
    context.mock_api.register(
        "/admin/dhcps?form=reservation", "get", EMPTY_RESULT
    )
    context.mock_api.register(
        "/admin/dhcps?form=reservation",
        "add",
        {"error_code": "0", "result": {}},
    )


# -- When steps --


@when("I run dhcp assigned")
def step_run_dhcp_assigned(context):
    args = argparse.Namespace(output_json=False, lan=None)
    run_command(context, cmd_dhcp_assigned, context.router, args)


@when("I run dhcp assigned --lan LAN")
def step_run_dhcp_assigned_lan(context):
    args = argparse.Namespace(output_json=False, lan="LAN")
    run_command(context, cmd_dhcp_assigned, context.router, args)


@when("I run dhcp assigned with --json")
def step_run_dhcp_assigned_json(context):
    args = argparse.Namespace(output_json=True, lan=None)
    run_command(context, cmd_dhcp_assigned, context.router, args)


@when("I run dhcp reserved")
def step_run_dhcp_reserved(context):
    args = argparse.Namespace(output_json=False, lan=None)
    run_command(context, cmd_dhcp_reserved, context.router, args)


@when("I run dhcp reserved --lan LAN")
def step_run_dhcp_reserved_lan(context):
    args = argparse.Namespace(output_json=False, lan="LAN")
    run_command(context, cmd_dhcp_reserved, context.router, args)


@when("I run dhcp reserved with --json")
def step_run_dhcp_reserved_json(context):
    args = argparse.Namespace(output_json=True, lan=None)
    run_command(context, cmd_dhcp_reserved, context.router, args)


@when("I run dhcp reserve --ip 192.168.0.50 --mac AA:BB:CC:DD:EE:FF")
def step_run_dhcp_reserve_new(context):
    args = argparse.Namespace(
        ip="192.168.0.50",
        mac="AA:BB:CC:DD:EE:FF",
        name=None,
        lan=None,
        disable=False,
        no_bind=False,
    )
    run_command(context, cmd_dhcp_reserve, context.router, args)


@when('I run dhcp reserve --ip 192.168.0.10 --name "new name"')
def step_run_dhcp_reserve_update(context):
    args = argparse.Namespace(
        ip="192.168.0.10",
        mac=None,
        name="new name",
        lan=None,
        disable=False,
        no_bind=False,
    )
    run_command(context, cmd_dhcp_reserve, context.router, args)


@when("I run dhcp reserve --ip 192.168.0.50 without MAC")
def step_run_dhcp_reserve_no_mac(context):
    args = argparse.Namespace(
        ip="192.168.0.50",
        mac=None,
        name=None,
        lan=None,
        disable=False,
        no_bind=False,
    )
    run_command(context, cmd_dhcp_reserve, context.router, args)


@when("I run dhcp unreserve --ip 192.168.0.10")
def step_run_dhcp_unreserve(context):
    args = argparse.Namespace(ip="192.168.0.10")
    run_command(context, cmd_dhcp_unreserve, context.router, args)


@when("I run dhcp unreserve --ip 192.168.0.99")
def step_run_dhcp_unreserve_not_found(context):
    args = argparse.Namespace(ip="192.168.0.99")
    run_command(context, cmd_dhcp_unreserve, context.router, args)
