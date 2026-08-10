"""Step definitions for firmware commands."""

import argparse
import json
from unittest.mock import MagicMock, patch

from behave import given, then, when

from homenet import cmd_firmware_check
from tests.environment import run_command

SUPPORT_PAGE_TEMPLATE = """
<html><body>
<div>ER605(UN)_V2.20_{version} Build 20260721</div>
</body></html>
"""


@given('a router with firmware version "{version}"')
def step_router_with_firmware(context, version):
    context.mock_api.register(
        "/admin/firmware?form=upgrade",
        "get",
        {
            "error_code": "0",
            "result": {
                "hardware_version": "ER605 v2.20",
                "model": "ER605",
                "firmware_version": version,
            },
        },
    )


@given('the latest firmware available is "{version}"')
def step_latest_firmware(context, version):
    context.support_page_html = SUPPORT_PAGE_TEMPLATE.format(version=version)


@given("the support page is unreachable")
def step_support_unreachable(context):
    context.support_page_html = None


@when("I run firmware check")
def step_run_firmware_check(context):
    args = argparse.Namespace(output_json=False)
    _run_with_mocked_fetch(context, args)


@when("I run firmware check with --json")
def step_run_firmware_check_json(context):
    args = argparse.Namespace(output_json=True)
    _run_with_mocked_fetch(context, args)


def _run_with_mocked_fetch(context, args):
    import requests as req

    html = getattr(context, "support_page_html", None)
    if html is None:
        mock_get = MagicMock(
            side_effect=req.exceptions.ConnectionError("unreachable")
        )
    else:
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        mock_get = MagicMock(return_value=mock_resp)

    with patch("homenet.requests.get", mock_get):
        run_command(context, cmd_firmware_check, context.router, args)


@then('the JSON field "{field}" is true')
def step_json_field_true(context, field):
    data = json.loads(context.stdout_text.strip())
    assert data.get(field) is True, (
        f"Expected {field}=true, got {data.get(field)}"
    )


@then('the JSON field "{field}" is false')
def step_json_field_false(context, field):
    data = json.loads(context.stdout_text.strip())
    assert data.get(field) is False, (
        f"Expected {field}=false, got {data.get(field)}"
    )
