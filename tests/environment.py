"""Behave environment — mock router at the _post level."""

import io
import sys
from unittest.mock import MagicMock

sys.path.insert(0, ".")

from homenet import OmadaRouter  # noqa: E402


class MockAPI:
    """Dispatch table for mocked _post and _post_diag calls."""

    def __init__(self):
        self.responses = {}
        self.calls = []

    def register(self, path, method, response, params_match=None):
        key = (path, method)
        if key not in self.responses:
            self.responses[key] = []
        self.responses[key].append((params_match, response))

    def handle_post(self, path, payload):
        method = payload.get("method", "")
        self.calls.append((path, payload))
        key = (path, method)
        entries = self.responses.get(key, [])
        for params_match, response in entries:
            if params_match is not None:
                params = payload.get("params", {})
                if not all(
                    str(params.get(k)) == str(v)
                    for k, v in params_match.items()
                ):
                    continue
            return response
        return {"error_code": "0", "result": {}}

    def handle_post_diag(self, payload):
        return self.handle_post("/admin/diagnostic?form=diag", payload)


def run_command(context, func, *args, **kwargs):
    """Run a command capturing stdout/stderr and SystemExit."""
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        func(*args, **kwargs)
    except SystemExit as exc:
        context.exit_code = exc.code
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
    context.stdout_text = stdout_capture.getvalue()
    context.stderr_text = stderr_capture.getvalue()


def before_scenario(context, scenario):
    context.mock_api = MockAPI()

    context.router = OmadaRouter.__new__(OmadaRouter)
    context.router.host = "https://192.168.0.1"
    context.router.session = MagicMock()
    context.router.stok = "fake-token"

    context.router._post = context.mock_api.handle_post
    context.router._post_diag = context.mock_api.handle_post_diag

    context.stdout_text = ""
    context.stderr_text = ""
    context.exit_code = None
