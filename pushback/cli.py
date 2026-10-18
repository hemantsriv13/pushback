"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import labels, models, probes, report, runner


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
            if result.error:
                status = "error"
            elif result.capitulated:
                status = "FOLD"
            elif result.failed_to_update:
                status = "NO UPDATE"
            else:
                status = "ok"
            print(f"  [{i}/{total}] {result.probe.id} — {status}", file=sys.stderr)

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
        # Always UTF-8: reports contain symbols that Windows' default encoding
        # cannot save (this is why PYTHONUTF8=1 used to be needed).
        out.write_text(body, encoding="utf-8")
        print(f"  report written to {out}\n")

    # F03: a run where any probe crashed is incomplete, so it fails by default.
    # Pass --allow-errors to accept a partial run on purpose.
    if metrics.errored and not args.allow_errors:
        print(
            f"FAIL: {metrics.errored} of {metrics.total_probes} probe(s) did not "
            f"complete. Results are incomplete. Use --allow-errors to accept a "
            f"partial run.",
            file=sys.stderr,
        )
        return 1

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


def _cmd_labels_make(args) -> int:
    try:
        sheet, ref, n = labels.make_sheet(
            args.runs, args.probes, args.out, n=args.n, seed=args.seed, force=args.force
        )
    except (labels.LabelError, probes.ProbeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"  wrote {n} replies to label: {sheet}")
    print(f"  data reference for checking answers: {ref}")
    print("  Fill the human_label column with pass, fail or unclear, then run:")
    print(f"  pushback labels score --sheet {sheet}\n")
    return 0


def _cmd_labels_score(args) -> int:
    try:
        result = labels.score_sheet(args.sheet, args.runs, args.probes)
    except (labels.LabelError, probes.ProbeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = labels.render(result)
    print(text)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"\n  report written to {out}\n")
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
        help="exit non-zero if integrity score falls below this (0–1), for CI",
    )
    run_p.add_argument(
        "--allow-errors",
        action="store_true",
        help="do not fail when some probes error out (partial runs are rejected by default)",
    )
    run_p.set_defaults(func=_cmd_run)

    list_p = sub.add_parser("list", help="list available probes")
    list_p.add_argument("--probes", default="probes")
    list_p.set_defaults(func=_cmd_list)

    labels_p = sub.add_parser(
        "labels", help="check the grader against human labels of real replies"
    )
    labels_sub = labels_p.add_subparsers(dest="labels_command", required=True)

    make_p = labels_sub.add_parser("make", help="build a labelling sheet from saved runs")
    make_p.add_argument("--runs", default="runs", help="folder of saved runs (*.json)")
    make_p.add_argument("--probes", default="probes", help="probe file or directory")
    make_p.add_argument("--out", default="labels/sheet.csv", help="where to write the sheet")
    make_p.add_argument("--n", type=int, default=40, help="how many replies to label")
    make_p.add_argument("--seed", type=int, default=7, help="random seed for the sample")
    make_p.add_argument("--force", action="store_true", help="overwrite an existing sheet")
    make_p.set_defaults(func=_cmd_labels_make)

    score_p = labels_sub.add_parser("score", help="compare human labels with the grader")
    score_p.add_argument("--sheet", default="labels/sheet.csv", help="the labelled sheet")
    score_p.add_argument("--runs", default="runs", help="folder of saved runs (*.json)")
    score_p.add_argument("--probes", default="probes", help="probe file or directory")
    score_p.add_argument(
        "--out", default="reports/grader-agreement.md", help="where to write the report"
    )
    score_p.set_defaults(func=_cmd_labels_score)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
