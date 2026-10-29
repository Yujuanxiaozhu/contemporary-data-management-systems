from pathlib import Path
import shutil
import subprocess


def test_client_intent_keys_preserved_on_failure_and_new_after_success():
    node = shutil.which('node')
    assert node, 'Node is required to verify the native JavaScript client contract'
    r = subprocess.run([node, 'tests/slice3_client_contract.js'], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'SLICE3_CLIENT_INTENT_RETRY_AND_NEW_INTENT=PASS' in r.stdout


def test_changed_javascript_syntax():
    node = shutil.which('node')
    assert node
    for path in [Path('app/static/management.js'), Path('app/static/question-bank.js')]:
        r = subprocess.run([node, '--check', str(path)], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
