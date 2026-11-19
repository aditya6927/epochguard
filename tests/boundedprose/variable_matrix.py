"""005H authored synthetic inputs/expectations; no authorization logic."""
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path

PYTHON_FORMS = (
    "The latest stable Python 3 release for Windows listed on Python.org is {v}.",
    "Python.org currently lists Python {v} as its latest stable Windows release.",
    "Python.org lists Python {v} as its latest stable Windows release.",
    "Python.org lists {v} as the latest stable Windows release.",
    "Python.org lists Python {v} as its latest stable release for Windows.")
PYPI_FORMS = (
    "The version reported for requests by the PyPI JSON API is {v}.",
    "PyPI reports requests version {v}.",
    "The PyPI JSON API reports requests version {v}.",
    "According to the PyPI JSON API, the version of requests is {v}.")
PAIRS = (("lower", "3.0.1", "0.0.1"), ("python-only", "3.0.2", "0.0.1"),
         ("pypi-only", "3.0.2", "0.0.2"), ("upper", "3.99.999", "999.999.999"))


@dataclass(frozen=True)
class Profile:
    name: str
    python: str = "3.0.1"
    pypi: str = "0.0.1"
    fault: str = "none"
    mode: str = "healthy"


@dataclass(frozen=True)
class Case:
    name: str
    text: str
    outcome: str
    sources: tuple[int, int]
    reasons: tuple[str, ...]
    route: str = "ingress"
    relay_fault: str = "none"


# Expected reasons follow primary_label(), validate_page(), pypi_version() and
# verify_claim(); malformed evidence is never assumed to be a contradiction.
NEGATIVES = (
    ("python-unavailable", "python", "RETRIEVAL_FAILURE"),
    ("pypi-malformed", "pypi", "INSUFFICIENT_EVIDENCE"),
    ("python-leading-zero", "python", "INSUFFICIENT_EVIDENCE"),
    ("python-major", "python", "INSUFFICIENT_EVIDENCE"),
    ("python-ambiguous", "python", "AMBIGUOUS_EVIDENCE"),
    ("pypi-leading-zero", "pypi", "INSUFFICIENT_EVIDENCE"),
    ("pypi-suffix", "pypi", "INSUFFICIENT_EVIDENCE"),
    ("pypi-numeric", "pypi", "INSUFFICIENT_EVIDENCE"),
    ("pypi-project", "pypi", "INSUFFICIENT_EVIDENCE"),
    ("pypi-yanked", "pypi", "INSUFFICIENT_EVIDENCE"),
    ("python-url", "python", "RETRIEVAL_FAILURE"),
    ("pypi-mode", "pypi", "RETRIEVAL_FAILURE"),
    ("ahead-python", "python", "CLAIM_AHEAD_OF_SOURCE"),
    ("ahead-pypi", "pypi", "CLAIM_AHEAD_OF_SOURCE"))


def profiles():
    return [*(Profile(name, py, pi) for name, py, pi in PAIRS),
            *(Profile(name+"-faults", py, pi, fault="source-faults", mode="negative") for name,py,pi in PAIRS),
            *(Profile(name, fault=name, mode="negative") for name, _, _ in NEGATIVES[2:]),
            Profile("receipt-v2", mode="receipts")]


def older(version):
    # Every selected version has a nonzero numeric component to decrement.
    values = list(map(int, version.split(".")))
    for index in (2, 1, 0):
        if values[index]:
            values[index] -= 1
            return ".".join(map(str, values))
    raise ValueError("no older fixture version")


def cases(profile):
    py = PYTHON_FORMS[1].format(v=profile.python)
    pi = PYPI_FORMS[1].format(v=profile.pypi)
    both = py+"\n"+pi
    matched = ("MATCHED_PRIMARY_LABEL", "MATCHED_PYPI_VERSION")
    if profile.mode == "negative":
        if profile.fault == "source-faults":
            return [Case("python-unavailable",py,"UNAVAILABLE",(1,0),("RETRIEVAL_FAILURE",)),
                    Case("pypi-malformed",pi,"UNAVAILABLE",(0,1),("INSUFFICIENT_EVIDENCE",))]
        _, policy, reason = next(row for row in NEGATIVES if row[0] == profile.fault)
        text = py if policy == "python" else pi
        if profile.fault == "ahead-python": text = PYTHON_FORMS[1].format(v="3.0.2")
        if profile.fault == "ahead-pypi": text = PYPI_FORMS[1].format(v="0.0.2")
        return [Case(profile.name, text, "UNAVAILABLE", (1, 0) if policy == "python" else (0, 1), (reason,))]
    if profile.mode == "receipts":
        return [Case("receipt-"+fault, both, "ALLOW" if fault == "none" else "INGRESS_REFUSED",
                     (1, 1), matched, "ingress-faults", fault)
                for fault in ("none", "mac", "body", "policy", "request-field", "replay")]
    result = [Case(f"python-form-{i}", form.format(v=profile.python), "ALLOW", (1, 0), (matched[0],))
              for i, form in enumerate(PYTHON_FORMS)]
    result += [Case(f"pypi-form-{i}", form.format(v=profile.pypi), "ALLOW", (0, 1), (matched[1],))
               for i, form in enumerate(PYPI_FORMS)]
    result += [Case("two-supported", both, "ALLOW", (1, 1), matched),
        Case("older-python", PYTHON_FORMS[1].format(v=older(profile.python))+"\n"+pi,
             "REJECT", (1, 1), ("OLDER_THAN_PRIMARY_LABEL", matched[1])),
        Case("older-pypi", py+"\n"+PYPI_FORMS[1].format(v=older(profile.pypi)),
             "REJECT", (1, 1), (matched[0], "OLDER_THAN_PYPI_VERSION")),
        Case("neighbor", both+" The Moon is made of cheese.", "UNAVAILABLE", (0, 0), ()),
        Case("repeat-python", py+"\n"+PYTHON_FORMS[2].format(v=older(profile.python)), "UNAVAILABLE", (0, 0), ()),
        Case("repeat-pypi", pi+"\n"+PYPI_FORMS[2].format(v=profile.pypi), "UNAVAILABLE", (0, 0), ()),
        Case("missing-plugin", both, "INGRESS_REFUSED", (0, 0), (), "ingress-unsafe")]
    return result


def sha(value):
    return hashlib.sha256(value).hexdigest()


def runtime_hash(verifier, bounded, comparison):
    roots = (("verifier", verifier), ("boundedprose", bounded), ("gatecompare", comparison))
    return sha(b"".join(label.encode()+b"/"+p.relative_to(root).as_posix().encode()+b"\0"+
                        p.read_bytes().replace(b"\r\n", b"\n")
                        for label, root in roots for p in sorted(root.glob("*.py") if label != "verifier" else root.rglob("*.py"))))


def validate(profile, client, observed):
    """Qualification assertions only; the protected processes already decided."""
    expected=cases(profile)
    rows=client["cases"]
    if (not observed["fixture"] or not observed["simulated_transports"] or observed["active"] or
        observed["profile"]!=profile.name or [r["case"] for r in rows]!=[c.name for c in expected]):
        raise ValueError("measurement denominator or fixture mismatch")
    index=0
    totals={"python":0,"pypi":0}
    urls={"python-windows-latest-v1":"https://www.python.org/downloads/windows/",
          "pypi-requests-reported-v1":"https://pypi.org/pypi/requests/json"}
    for case,row in zip(expected,rows):
        if (row["outcome"]!=case.outcome or row["status"]!={"ALLOW":200,"REJECT":403,"UNAVAILABLE":503,"INGRESS_REFUSED":503}[case.outcome]
            or row["candidate_sha256"]!=sha(case.text.encode()) or row["content_released"]!=(case.outcome=="ALLOW")
            or row["approved_content_sha256"]!=(sha(case.text.encode()) if case.outcome=="ALLOW" else None)):
            raise ValueError("protected outcome/content mismatch")
        if case.route=="ingress-unsafe": continue
        record=observed["records"][index]
        index+=1
        wanted={"python":case.sources[0],"pypi":case.sources[1]}
        if (not record["completed"] or record["candidate_sha256"]!=row["candidate_sha256"] or
            record["source_invocations"]!=wanted or record["claim_reasons"]!=list(case.reasons)):
            raise ValueError("independent verification mismatch")
        for name in totals: totals[name]+=wanted[name]
        if not case.reasons:
            if record["coverage"]!="UNCERTAIN" or record["claims"] or record["canonical_sha256"] is not None:
                raise ValueError("partial grammar admission")
            if record["reason"]!=("REPEATED_CLAIM" if case.name.startswith("repeat") else "UNRECOGNIZED_CONTENT"):
                raise ValueError("grammar refusal reason")
        else:
            verdict="CONTRADICTED" if case.outcome=="REJECT" else "INSUFFICIENT" if profile.mode=="negative" else "SUPPORTED"
            if record["coverage"]!="COMPLETE" or record["verdict"]!=verdict:
                raise ValueError("evidence verdict mismatch")
        for claim in record["claims"]:
            for evidence in claim["evidence"]:
                python=claim["policy_id"]=="python-windows-latest-v1"
                identity=f"{evidence['url']}|{evidence['retrieval_mode']}|{evidence['retrieval_id']}|{evidence['content_sha256']}"
                if (evidence["url"]!=urls[claim["policy_id"]] or evidence["retrieval_mode"]!="fixture" or
                    evidence["observed_version"]!=(profile.python if python else profile.pypi) or
                    evidence["evidence_id"]!=sha(identity.encode()) or evidence["observed_at"]!=evidence["retrieved_at"]):
                    raise ValueError("source/version identity mismatch")
    if index!=len(observed["records"]) or totals!=observed["source_invocations"]:
        raise ValueError("uncorrelated records or source calls")
    return {"profile":asdict(profile),"case_count":len(rows),"source_invocations":totals,
            "outcomes":{name:sum(r["outcome"]==name for r in rows) for name in ("ALLOW","REJECT","UNAVAILABLE","INGRESS_REFUSED")},
            "expectations_met":True}
