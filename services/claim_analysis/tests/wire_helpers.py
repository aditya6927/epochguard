"""Build explicit NEW wire fixtures from canonical test expectations only.

Not used by production. Real model outputs are never repaired or converted from
the old offset-bearing format; that format is rejected by Identification.
"""
from copy import deepcopy


def identification(canonical):
    value = deepcopy(canonical)
    value["schema_version"] = "004a.identification.v1"
    for claim in value["claims"]:
        claim.pop("start", None)
        claim.pop("end", None)
    return value
