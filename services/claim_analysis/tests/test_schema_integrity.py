from pathlib import Path

import pytest

from claim_analysis.schema_integrity import SCHEMAS, check_bytes


@pytest.mark.parametrize("name", SCHEMAS)
def test_schema_bytes_are_pinned_lf(name):
    data = (Path(__file__).parents[1] / name).read_bytes()
    check_bytes(name, data)
    with pytest.raises(ValueError, match="LF"):
        check_bytes(name, data.replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match="hash mismatch"):
        check_bytes(name, b" " + data)
