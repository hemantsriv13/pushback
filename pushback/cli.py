"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import models, probes, report, runner


def _cmd_run(args) -> int:
    try:
        suite = probes.load(args.probes)
    except probes.ProbeError as exc:
        print(f"error loading probes: {exc}", file=sys.stderr)
        return 2

    if args.suite:
        suite = [p for p in suite if p.suite == args.suite]
    if args.probe:
        suite = [p for p in suite if p.id in args.probe]
    if not suite:
        print("error: no probes matched the given filters", file=sys.stderr)
        return 2

    try:
        model = models.build(args.model)
    except models.ModelError as exc:
        print(f"error building model: {exc}", file=sys.stderr)
        return 2

    def progress(i, total, result):
        if not args.quiet:
            status = "error" if result.error else ("FOLD" if result.capitulated else "ok")
            print(f"  [{i}/{total}] {result.probe.id} \u2014 {status}", file=sys.stderr)

    results = runner.run(model, suite, on_progress=progress)
    metrics = runner.score(results, model.name)

    print(report.console(metrics, results, verbose=args.verbose))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        body = (
            report.to_json(metrics, results)
            if out.suffix == ".json"
            else report.markdown(metrics, results)
        )
        out.write_text(body)
        print(f"  report written to {out}\n")

    if args.fail_under is not None:
        actual = metrics.integrity_score
        if actual is None:
            print("error: integrity score undefined, cannot gate", file=sys.stderr)
            return 1
        if actual < args.fail_under:
            print(
                f"FAIL: integrity {actual:.2%} below threshold {args.fail_under:.2%}",
                file=sys.stderr,
            )
            return 1
    return 0


def _cmd_list(args) -> int:
    try:
        suite = probes.load(args.probes)
    except probes.ProbeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for p in suite:
        tags = ", ".join(sorted({t.tag.value for t in p.turns}))
        print(f"{p.suite:<20} {p.id:<28} {len(p.turns)} turns  [{tags}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pushback",
        description="Measure whether a model abandons correct answers under pressure.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run a probe suite against a model")
    run_p.add_argument("--model", default="mock:sycophantic", help="provider:name")
    run_p.add_argument("--probes", default="probes", help="probe file or directory")
    run_p.add_argument("--suite", help="only run this suite")
    run_p.add_argument("--probe", action="append", help="only run this probe id")
    run_p.add_argument("--out", help="write report to .md or .json")
    run_p.add_argument("--verbose", action="store_true", help="print full transcripts")
    run_p.add_argument("--quiet", action="store_true", help="suppress progress")
    run_p.add_argument(
        "--fail-under",
        type=float,
        help="exit non-zero if integrity score falls below this (0\u20131), for CI",
    )
    run_p.set_defaults(func=_cmd_run)

    list_p = sub.add_parser("list", help="list available probes")
    list_p.add_argument("--probes", default="probes")
    list_p.set_defaults(func=_cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
