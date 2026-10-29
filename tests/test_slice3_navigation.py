import shutil
import subprocess
import pytest


@pytest.mark.parametrize('scenario', [
    'revision_retry_same_key', 'revision_wrong_target', 'revision_back_forward_cache',
    'picker_stale_document', 'picker_retry_same_key', 'family_target_confirmation'])
def test_navigation_acknowledgement_and_retry(scenario):
    node = shutil.which('node')
    assert node
    result = subprocess.run([node, 'tests/slice3_navigation_contract.js', scenario],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'NAVIGATION_ACK_' + scenario + '=PASS' in result.stdout


@pytest.mark.parametrize('scenario', [
    'revision_bfcache_confirmed', 'revision_bfcache_unconfirmed',
    'picker_bfcache_confirmed', 'picker_bfcache_unconfirmed',
    'family_bfcache_confirmed', 'family_bfcache_unconfirmed'])
def test_navigation_bfcache_roundtrip(scenario):
    node = shutil.which('node')
    assert node
    result = subprocess.run([node, 'tests/slice3_navigation_contract.js', scenario],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'NAVIGATION_ACK_' + scenario + '=PASS' in result.stdout


@pytest.mark.parametrize('scenario', [
    'revision_revisit_failure', 'picker_revisit_failure',
    'revision_revisit_cancelled', 'picker_revisit_cancelled',
    'picker_unconfirmed_changed_payload'])
def test_navigation_confirmed_revisit_and_pending_payload(scenario):
    node = shutil.which('node')
    assert node
    result = subprocess.run([node, 'tests/slice3_navigation_contract.js', scenario],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'NAVIGATION_ACK_' + scenario + '=PASS' in result.stdout
