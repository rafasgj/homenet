"""Step definitions for connection error scenarios."""

from unittest.mock import patch

import requests.exceptions
from behave import given, when

from homenet import main
from tests.environment import run_command


@given("the router's TLS certificate has changed")
def step_tls_cert_changed(context):
    context.login_side_effect = requests.exceptions.SSLError(
        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
        "self-signed certificate"
    )


@given("the router rejects the password")
def step_wrong_password(context):
    context.login_side_effect = RuntimeError("Invalid username or password")


@when("I run any command against the router")
def step_run_command_against_router(context):
    with (
        patch("sys.argv", ["homenet", "--host", "https://192.168.0.1", "wan"]),
        patch("homenet.keyring.get_password", return_value="fake"),
        patch("homenet.OmadaRouter.__init__", return_value=None),
        patch(
            "homenet.OmadaRouter.login",
            side_effect=context.login_side_effect,
        ),
        patch("homenet.OmadaRouter.logout"),
    ):
        run_command(context, main)
