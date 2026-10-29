"""Actual JS event-handler execution with DOM doubles, not browser E2E."""
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('scenario', [
    'restore_cancel', 'restore_success', 'restore_refresh_failure', 'restore_unknown_retry',
    'picker_add', 'picker_update', 'picker_reload_failure',
    'revision_retry', 'revision_navigation_failure', 'form_refresh_failure'])
def test_page_dom_handlers(scenario):
    node = shutil.which('node')
    assert node
    result = subprocess.run([node, 'tests/slice3_dom_contract.js', scenario],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'SLICE3_DOM_' + scenario + '=PASS' in result.stdout
