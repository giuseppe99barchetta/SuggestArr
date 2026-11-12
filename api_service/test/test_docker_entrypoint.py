"""The container entrypoint starts uvicorn without passing arguments through eval."""
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ENTRYPOINT = Path(__file__).resolve().parents[2] / 'docker' / 'docker_entrypoint.sh'
SH = shutil.which('sh')

pytestmark = pytest.mark.skipif(SH is None, reason='needs a POSIX sh')


def run_entrypoint(tmp_path, *args, **env):
    fake = tmp_path / 'uvicorn'
    fake.write_text('#!/bin/sh\nfor a in "$@"; do echo "ARG:$a"; done\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    environment = {**os.environ, 'PATH': f'{tmp_path}{os.pathsep}{os.environ["PATH"]}',
                   'SUGGESTARR_APP_DIR': str(tmp_path), **env}
    environment.pop('SUGGESTARR_PORT', None) if 'SUGGESTARR_PORT' not in env else None
    result = subprocess.run([SH, str(ENTRYPOINT), *args], capture_output=True, text=True, env=environment, timeout=30)
    return result.returncode, [line[4:] for line in result.stdout.splitlines() if line.startswith('ARG:')]


def test_default_command_listens_on_the_configured_port(tmp_path):
    code, args = run_entrypoint(tmp_path, SUGGESTARR_PORT='5099')
    assert code == 0
    assert args == ['api_service.app:asgi_app', '--host', '0.0.0.0', '--port', '5099', '--log-level', 'info']


def test_default_port_is_5000(tmp_path):
    assert run_entrypoint(tmp_path)[1][4] == '5000'


def test_container_arguments_replace_the_default_and_are_never_evaluated(tmp_path):
    marker = tmp_path / 'pwned'
    code, args = run_entrypoint(tmp_path, '--port', '8080', f'; touch {marker}', '$(touch ' + str(marker) + ')')
    assert code == 0
    assert args[1:3] == ['--port', '8080']
    assert not marker.exists()                       # no eval: the text stays a plain argument
    assert args[3] == f'; touch {marker}'
