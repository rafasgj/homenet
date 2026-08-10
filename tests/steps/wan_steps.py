"""Step definitions for WAN commands."""

import argparse
import json
from unittest.mock import patch

from behave import given, then, when

from homenet import (
    cmd_wan,
    cmd_wan_config,
    cmd_wan_stats,
    cmd_wan_test,
)
from tests.environment import run_command

WAN_INTERFACES = {
    "error_code": "0",
    "result": {
        "normal": [
            {
                "t_proto": "pppoe",
                "ipaddr": "187.91.221.207",
                "dns2": "8.8.8.8",
                "t_type": "pppoe",
                "macaddr": "8C-90-2D-16-6A-3A",
                "dns1": "1.1.1.1",
                "t_label": "WAN",
                "netmask": "255.255.255.255",
                "gateway": "152.255.239.143",
                "t_name": "WAN1",
                "t_isup": True,
                "second_conn": False,
            },
            {
                "t_proto": "dhcp",
                "ipaddr": "192.168.0.206",
                "dns2": "8.8.8.8",
                "t_type": "physical",
                "macaddr": "8C-90-2D-16-6A-3B",
                "t_linktype": "dhcp",
                "dns1": "1.1.1.1",
                "t_label": "WAN/LAN1",
                "netmask": "255.255.255.0",
                "gateway": "192.168.0.1",
                "t_name": "WAN2",
                "t_isup": True,
                "second_conn": False,
            },
        ]
    },
}

WAN_MODE = {
    "error_code": "0",
    "result": {
        "wan_numbers": ["1", "2"],
        "wanmode": "2",
        "wan_names": [
            {"type": "0", "logical": "1", "index": "1", "name": "WAN"},
            {
                "type": "1",
                "logical": "2",
                "index": "2",
                "name": "WAN/LAN1",
            },
            {
                "type": "1",
                "logical": "3",
                "index": "3",
                "name": "WAN/LAN2",
            },
        ],
        "wanmax": 4,
        "singlewan": 0,
    },
}

WAN1_CONFIG = {
    "error_code": "0",
    "result": {
        "wan_id": "1",
        "proto": "pppoe",
        "uplink": "250000",
        "downlink": "500000",
        "mtu": "1492",
        "dns1": "1.1.1.1",
        "dns2": "8.8.8.8",
    },
}

WAN2_CONFIG = {
    "error_code": "0",
    "result": {
        "wan_id": "2",
        "proto": "dhcp",
        "uplink": "50000",
        "downlink": "300000",
        "mtu": "1500",
        "dns1": "1.1.1.1",
        "dns2": "8.8.8.8",
    },
}

INTERFACE_STATS = {
    "error_code": "0",
    "result": [
        {
            "zone": "WAN1",
            "rx_bytes": "14040277",
            "tx_bytes": "1758958",
            "rx_bps": 1,
            "tx_bps": 1,
            "rx_pps": 3,
            "tx_pps": 3,
            "rx_pkts": "13630",
            "tx_pkts": "13003",
        },
        {
            "zone": "WAN2",
            "rx_bytes": "9084324",
            "tx_bytes": "24580071",
            "rx_bps": 30,
            "tx_bps": 42,
            "rx_pps": 53,
            "tx_pps": 54,
            "rx_pkts": "32116",
            "tx_pkts": "40206",
        },
    ],
}


def _register_wan_interfaces(context):
    context.mock_api.register(
        "/admin/interface?form=status3", "get", WAN_INTERFACES
    )


def _register_wan_mode(context):
    context.mock_api.register(
        "/admin/interface_wan?form=wanmode", "get", WAN_MODE
    )


def _register_wan_bandwidth(context):
    _register_wan_mode(context)
    context.mock_api.register(
        "/admin/interface_wan?form=wanconfig",
        "get",
        WAN1_CONFIG,
        params_match={"wan_id": "1"},
    )
    context.mock_api.register(
        "/admin/interface_wan?form=wanconfig",
        "get",
        WAN2_CONFIG,
        params_match={"wan_id": "2"},
    )


@given("a router with WAN interfaces")
def step_router_with_wans(context):
    _register_wan_interfaces(context)
    _register_wan_bandwidth(context)


@given("a router with no WAN interfaces")
def step_router_no_wans(context):
    context.mock_api.register(
        "/admin/interface?form=status3",
        "get",
        {"error_code": "0", "result": {"normal": []}},
    )
    context.mock_api.register(
        "/admin/interface_wan?form=wanmode",
        "get",
        {
            "error_code": "0",
            "result": {
                "wan_numbers": [],
                "wanmode": "2",
                "wan_names": [],
                "wanmax": 4,
                "singlewan": 0,
            },
        },
    )


@given("WAN/LAN2 is enabled but not connected")
def step_wan_lan2_enabled(context):
    mode = {
        "error_code": "0",
        "result": dict(WAN_MODE["result"], wan_numbers=["1", "2", "3"]),
    }
    context.mock_api.responses.pop(
        ("/admin/interface_wan?form=wanmode", "get"), None
    )
    context.mock_api.register("/admin/interface_wan?form=wanmode", "get", mode)


@given("the router has interface statistics")
def step_router_has_stats(context):
    context.mock_api.register(
        "/admin/ifstat?form=list", "get", INTERFACE_STATS
    )


@given("WAN1 has bandwidth configuration")
def step_wan1_has_config(context):
    context.mock_api.register(
        "/admin/interface_wan?form=wanconfig",
        "set",
        {"error_code": "0", "result": {}},
    )


@given("ping returns a successful result")
def step_ping_success(context):
    context.mock_api.register(
        "/admin/diagnostic?form=diag",
        "start",
        {"error_code": "0", "result": {}},
    )
    context.mock_api.register(
        "/admin/diagnostic?form=diag",
        "continue",
        {
            "error_code": "0",
            "result": {
                "finish": "1",
                "my_result": "3 packets, 3 received, bytes=64",
            },
        },
    )


@given("ping returns a failure result")
def step_ping_failure(context):
    context.mock_api.register(
        "/admin/diagnostic?form=diag",
        "start",
        {"error_code": "0", "result": {}},
    )
    context.mock_api.register(
        "/admin/diagnostic?form=diag",
        "continue",
        {
            "error_code": "0",
            "result": {"finish": "1", "my_result": "0 received"},
        },
    )


# -- When steps --


@when("I run wan status")
def step_run_wan_status(context):
    args = argparse.Namespace(output_json=False)
    run_command(context, cmd_wan, context.router, args)


@when("I run wan status with --json")
def step_run_wan_status_json(context):
    args = argparse.Namespace(output_json=True)
    run_command(context, cmd_wan, context.router, args)


@when("I run wan stats")
def step_run_wan_stats(context):
    args = argparse.Namespace(output_json=False, clear=False)
    run_command(context, cmd_wan_stats, context.router, args)


@when("I run wan stats --clear")
def step_run_wan_stats_clear(context):
    context.mock_api.register(
        "/admin/ifstat?form=list",
        "clear",
        {"error_code": "0", "result": {}},
    )
    args = argparse.Namespace(output_json=False, clear=True)
    run_command(context, cmd_wan_stats, context.router, args)


@when("I run wan stats with --json")
def step_run_wan_stats_json(context):
    args = argparse.Namespace(output_json=True, clear=False)
    run_command(context, cmd_wan_stats, context.router, args)


@when("I run wan config WAN --downstream 500m --upstream 250m")
def step_run_wan_config_both(context):
    args = argparse.Namespace(
        wan_name="WAN",
        downstream="500m",
        upstream="250m",
        enable=None,
        disable=None,
        output_json=False,
    )
    run_command(context, cmd_wan_config, context.router, args)


@when("I run wan config WAN --downstream 300m")
def step_run_wan_config_downstream(context):
    args = argparse.Namespace(
        wan_name="WAN",
        downstream="300m",
        upstream=None,
        enable=None,
        disable=None,
        output_json=False,
    )
    run_command(context, cmd_wan_config, context.router, args)


@when("I run wan config --enable WAN/LAN2")
def step_run_wan_config_enable(context):
    context.mock_api.register(
        "/admin/interface_wan?form=wanmode",
        "set",
        {"error_code": "0", "result": {}},
    )
    args = argparse.Namespace(
        wan_name=None,
        downstream=None,
        upstream=None,
        enable=["WAN/LAN2"],
        disable=None,
        output_json=False,
    )
    run_command(context, cmd_wan_config, context.router, args)


@when("I run wan config --disable WAN/LAN1")
def step_run_wan_config_disable(context):
    context.mock_api.register(
        "/admin/interface_wan?form=wanmode",
        "set",
        {"error_code": "0", "result": {}},
    )
    args = argparse.Namespace(
        wan_name=None,
        downstream=None,
        upstream=None,
        enable=None,
        disable=["WAN/LAN1"],
        output_json=False,
    )
    run_command(context, cmd_wan_config, context.router, args)


@when("I run wan config with no options")
def step_run_wan_config_no_options(context):
    args = argparse.Namespace(
        wan_name=None,
        downstream=None,
        upstream=None,
        enable=None,
        disable=None,
        output_json=False,
    )
    run_command(context, cmd_wan_config, context.router, args)


@when("I run wan config --downstream 100m without WAN name")
def step_run_wan_config_no_name(context):
    args = argparse.Namespace(
        wan_name=None,
        downstream="100m",
        upstream=None,
        enable=None,
        disable=None,
        output_json=False,
    )
    run_command(context, cmd_wan_config, context.router, args)


@when("I run wan test")
def step_run_wan_test(context):
    args = argparse.Namespace(output_json=False, target=None)
    with patch("time.sleep"):
        run_command(context, cmd_wan_test, context.router, args)


@when("I run wan test with --json")
def step_run_wan_test_json(context):
    args = argparse.Namespace(output_json=True, target=None)
    with patch("time.sleep"):
        run_command(context, cmd_wan_test, context.router, args)


# -- Then steps --


@then('the output contains "{text}"')
def step_output_contains(context, text):
    assert text in context.stdout_text, (
        f"Expected '{text}' in output:\n{context.stdout_text}"
    )


@then('the error output contains "{text}"')
def step_error_contains(context, text):
    assert text in context.stderr_text, (
        f"Expected '{text}' in stderr:\n{context.stderr_text}"
    )


@then("the output is valid JSON")
def step_output_is_json(context):
    output = context.stdout_text.strip()
    try:
        context.json_output = json.loads(output)
    except json.JSONDecodeError:
        raise AssertionError(f"Output is not valid JSON:\n{output}")


@then("the output contains valid JSON")
def step_output_contains_json(context):
    output = context.stdout_text
    start = output.find("[")
    if start == -1:
        start = output.find("{")
    if start == -1:
        raise AssertionError(f"No JSON found in output:\n{output}")
    try:
        context.json_output = json.loads(output[start:])
    except json.JSONDecodeError:
        raise AssertionError(f"Output does not contain valid JSON:\n{output}")


@then("the JSON output has {count:d} entries")
def step_json_has_entries(context, count):
    if not hasattr(context, "json_output"):
        context.json_output = json.loads(context.stdout_text.strip())
    assert len(context.json_output) == count, (
        f"Expected {count} entries, got {len(context.json_output)}"
    )


@then('the API endpoint "{path}" was called with method "{method}"')
def step_api_called(context, path, method):
    for call_path, call_payload in context.mock_api.calls:
        if call_path == path and call_payload.get("method") == method:
            return
    calls = [(p, pl.get("method")) for p, pl in context.mock_api.calls]
    raise AssertionError(
        f"Expected call to {path} with method={method}. Calls made: {calls}"
    )
