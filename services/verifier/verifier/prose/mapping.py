"""Closed, case-sensitive proposition grammar; never model normalization."""

import re

from verifier.multiclaim.contract import PYTHON_POLICY, PYPI_POLICY
from verifier.multiclaim.coverage import qualify

VERSION = r"(3\.(?:0|[1-9][0-9]?)\.(?:0|[1-9][0-9]{0,2}))"
PACKAGE_VERSION = r"((?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2}))"
PYTHON_FORMS = (
    "Python.org currently lists Python {v} as its latest stable Windows release.",
    "Python.org lists Python {v} as its latest stable Windows release.",
    "Python.org lists {v} as the latest stable Windows release.",
    "Python.org lists Python {v} as its latest stable release for Windows.",
)
PYPI_FORMS = (
    "PyPI reports requests version {v}.",
    "The PyPI JSON API reports requests version {v}.",
    "According to the PyPI JSON API, the version of requests is {v}.",
)


def patterns(forms, version):
    return tuple(re.compile(re.escape(form).replace(re.escape("{v}"), version)) for form in forms)


REGISTRY = ((PYTHON_POLICY, patterns(PYTHON_FORMS, VERSION)),
            (PYPI_POLICY, patterns(PYPI_FORMS, PACKAGE_VERSION)))


def match(text):
    # Also admit the existing exact forms without altering their parser.
    claims, coverage = qualify(text)
    if coverage.status == "COMPLETE" and len(claims) == 1 and claims[0].source.source_text == text:
        return claims[0].policy_id, claims[0].version
    for policy, forms in REGISTRY:
        for form in forms:
            found = form.fullmatch(text)
            if found:
                return policy, found[1]
    return None


def canonical(policy, version):
    if policy == PYTHON_POLICY:
        return f"The latest stable Python 3 release for Windows listed on Python.org is {version}."
    if policy == PYPI_POLICY:
        return f"The version reported for requests by the PyPI JSON API is {version}."
    raise ValueError("unknown policy")
