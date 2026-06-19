"""fix_package_json_bare_jest also rescues a `test` script that runs a Jest spec
under plain `node` — the dominant p8 jest-globals failure.

`"test": "node todo.test.js"` makes `npm test` execute the spec with bare node,
leaving describe/it/test/jest undefined ("ReferenceError: it is not defined")
before any test runs. When jest is a declared dependency the runner must be jest.
"""
import json
from pathlib import Path

from mu.reflexes.javascript import fix_package_json_bare_jest


def _pkg(tmp_path, data):
    p = tmp_path / 'package.json'
    p.write_text(json.dumps(data))
    return tmp_path


def _test_script(tmp_path):
    return json.loads((tmp_path / 'package.json').read_text())['scripts']['test']


def test_node_run_testfile_switched_to_jest(tmp_path):
    _pkg(tmp_path, {
        'devDependencies': {'jest': '^29.0.0'},
        'scripts': {'test': 'node todo.test.js'},
    })
    assert fix_package_json_bare_jest(str(tmp_path)) is True
    assert _test_script(tmp_path) == 'npx jest --forceExit'


def test_node_run_spec_file_switched(tmp_path):
    _pkg(tmp_path, {
        'devDependencies': {'jest': '^29.0.0'},
        'scripts': {'test': 'node model.spec.js'},
    })
    assert fix_package_json_bare_jest(str(tmp_path)) is True
    assert _test_script(tmp_path) == 'npx jest --forceExit'


def test_node_running_app_is_left_alone(tmp_path):
    """`node server.js` in a non-test script must not be rewritten."""
    _pkg(tmp_path, {
        'devDependencies': {'jest': '^29.0.0'},
        'scripts': {'start': 'node server.js', 'test': 'npx jest'},
    })
    # test script already correct → only testRegex may be added; start untouched.
    fix_package_json_bare_jest(str(tmp_path))
    data = json.loads((tmp_path / 'package.json').read_text())
    assert data['scripts']['start'] == 'node server.js'
    assert data['scripts']['test'] == 'npx jest'


def test_node_modules_bin_jest_not_matched(tmp_path):
    """A node-invoked jest binary path is already correct — don't clobber it."""
    _pkg(tmp_path, {
        'devDependencies': {'jest': '^29.0.0'},
        'scripts': {'test': 'node_modules/.bin/jest todo.test.js'},
    })
    fix_package_json_bare_jest(str(tmp_path))
    assert _test_script(tmp_path) == 'node_modules/.bin/jest todo.test.js'


def test_no_jest_dependency_no_change(tmp_path):
    """Without jest as a dependency, don't impose jest."""
    _pkg(tmp_path, {
        'dependencies': {},
        'scripts': {'test': 'node todo.test.js'},
    })
    assert fix_package_json_bare_jest(str(tmp_path)) is False
