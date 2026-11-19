"""Read a local snapshot; emit sanitized JSON/HTML without contacting services."""
import argparse
from pathlib import Path
from .derive import from_result
from .importers import from_qualification
from .presentation import render


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "005D invalid arguments; values withheld\n")


def main():
    parser = SafeParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--kind", choices=("bounded-result", "qualification"), required=True)
    parser.add_argument("--evidence-profile", choices=("fixture", "live"), required=True)
    parser.add_argument("--record-index", type=int, choices=range(16), default=0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--html", type=Path)
    args = parser.parse_args()
    try:
        # Exclusive creation and path checks prevent overwriting input or history.
        outputs = [args.output] + ([args.html] if args.html else [])
        resolved = [p.resolve() for p in [args.input, *outputs]]
        if len(set(resolved)) != len(resolved) or any(p.exists() for p in outputs):
            raise ValueError("output exists")
        with args.input.open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError("input bound")
        report = (from_qualification(raw, profile=args.evidence_profile, record_index=args.record_index)
                  if args.kind == "qualification" else from_result(raw, profile=args.evidence_profile))
        data = report.model_dump_json(indent=2)+"\n"
        page = render(report) if args.html else None
        if len(data.encode()) > 65536:
            raise ValueError("output bound")
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(data)
        if page is not None:
            with args.html.open("x", encoding="utf-8") as stream:
                stream.write(page)
        print("005D diagnostic written: "+report.report_status+" / "+report.report_reason)
    except Exception:
        parser.exit(1, "005D reporting unavailable; no verification or release performed.\n")


if __name__ == "__main__":
    main()
