import re
from pathlib import Path

from ._common import _insert_py_imports  # noqa: F401

# Common third-party symbols and their import statements
# Key: symbol name, Value: import statement to add
_THIRDPARTY_IMPORTS: dict[str, str] = {
    # SQLAlchemy ORM
    'declarative_base': 'from sqlalchemy.orm import declarative_base',
    'Base': 'from sqlalchemy.orm import declarative_base\nBase = declarative_base()',
    'sessionmaker': 'from sqlalchemy.orm import sessionmaker',
    'Session': 'from sqlalchemy.orm import Session',
    'scoped_session': 'from sqlalchemy.orm import scoped_session',
    # SQLAlchemy core
    'Column': 'from sqlalchemy import Column',
    'Integer': 'from sqlalchemy import Integer',
    'String': 'from sqlalchemy import String',
    'Text': 'from sqlalchemy import Text',
    'DateTime': 'from sqlalchemy import DateTime',
    'Boolean': 'from sqlalchemy import Boolean',
    'Float': 'from sqlalchemy import Float',
    'ForeignKey': 'from sqlalchemy import ForeignKey',
    'create_engine': 'from sqlalchemy import create_engine',
    'Numeric': 'from sqlalchemy import Numeric',
    'Date': 'from sqlalchemy import Date',
    'Time': 'from sqlalchemy import Time',
    'LargeBinary': 'from sqlalchemy import LargeBinary',
    'PickleType': 'from sqlalchemy import PickleType',
    'Index': 'from sqlalchemy import Index',
    'UniqueConstraint': 'from sqlalchemy import UniqueConstraint',
    'PrimaryKeyConstraint': 'from sqlalchemy import PrimaryKeyConstraint',
    'CheckConstraint': 'from sqlalchemy import CheckConstraint',
    'event': 'from sqlalchemy import event',
    # Flask
    'Flask': 'from flask import Flask',
    'request': 'from flask import request',
    'jsonify': 'from flask import jsonify',
    'Blueprint': 'from flask import Blueprint',
    'render_template': 'from flask import render_template',
    'redirect': 'from flask import redirect',
    'url_for': 'from flask import url_for',
    'abort': 'from flask import abort',
    'current_app': 'from flask import current_app',
    'g': 'from flask import g',
    'session': 'from flask import session',
    'flash': 'from flask import flash',
    'send_file': 'from flask import send_file',
    'send_from_directory': 'from flask import send_from_directory',
    'make_response': 'from flask import make_response',
    'Response': 'from flask import Response',
    'stream_with_context': 'from flask import stream_with_context',
    'has_request_context': 'from flask import has_request_context',
    # Testing
    'pytest': 'import pytest',
    'client': 'from flask.testing import FlaskClient',
    'Client': 'from flask.testing import FlaskClient',
    'pytest_fixture': 'import pytest',
    'fixture': 'import pytest',
    # SQLAlchemy testing
    'SQLAlchemy': 'from flask_sqlalchemy import SQLAlchemy',
    # Common utilities
    'datetime': 'from datetime import datetime',
    'date': 'from datetime import date',
    'timedelta': 'from datetime import timedelta',
}

# Symbols that should NOT trigger this reflex (too generic or ambiguous)
_EXCLUDED_SYMBOLS = {
    'test', 'type', 'name', 'id', 'data', 'value', 'key', 'item', 'list',
    'dict', 'set', 'tuple', 'str', 'int', 'float', 'bool', 'bytes',
    'object', 'class', 'def', 'return', 'import', 'from', 'as',
}


def fix_python_missing_thirdparty_imports(file_path: str, lint_error: str) -> bool:
    """Add imports for common third-party symbols reported undefined.

    Scans lint/runtime errors for undefined third-party names (e.g.,
    ``undefined name 'declarative_base'`` or ``NameError: name 'Flask' is not defined``)
    and adds the appropriate import statement. Covers common web frameworks
    (Flask, SQLAlchemy) and testing utilities that the model frequently omits.
    Generic: driven entirely by the error text, not specific to any problem.
    """
    if not file_path.lower().endswith('.py'):
        return False
    
    # Extract undefined names from error messages
    undefined = set(re.findall(r"undefined name '(\w+)'", lint_error))
    undefined |= set(re.findall(r"NameError: name '(\w+)' is not defined", lint_error))
    
    if not undefined:
        return False
    
    # Filter to symbols we can fix and that aren't excluded
    to_fix = [name for name in undefined 
              if name in _THIRDPARTY_IMPORTS and name not in _EXCLUDED_SYMBOLS]
    
    if not to_fix:
        return False
    
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    
    # Check if already imported
    to_add = []
    for name in to_fix:
        import_stmt = _THIRDPARTY_IMPORTS[name]
        # Check if the name is already bound by any import
        if re.search(rf'\b{re.escape(name)}\b', text):
            # Check if it's actually imported, not just used
            name_pattern = rf'(?:import\s+{re.escape(name)}\b|from\s+\S+\s+import\s+[^\n]*\b{re.escape(name)}\b|import\s+\S+\s+as\s+{re.escape(name)}\b)'
            if not re.search(name_pattern, text):
                to_add.append(import_stmt)
        else:
            # For 'Base' which creates a variable, check if Base = declarative_base() exists
            if name == 'Base':
                if 'Base = declarative_base()' not in text and 'Base = ' not in text:
                    to_add.append(import_stmt)
            else:
                to_add.append(import_stmt)
    
    if not to_add:
        return False
    
    _insert_py_imports(file_path, to_add)
    print(f"==> [mu-agent] Reflex: added {len(to_add)} missing third-party import(s) to {file_path}: {to_add}")
    return True
