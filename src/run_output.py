"""Save one run and its plots together, with a small browser-friendly gallery."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from time import monotonic
from urllib.parse import quote

from src.config import resolved_config
from src.progress import status


def start_run(task, args):
    if args.plots:
        try:
            from src.plots import render_plots  # Check dependencies before running the experiment.
        except ImportError as exc:
            raise SystemExit("Plotting dependencies are missing. Run: python -m pip install -r requirements.txt") from exc
    status(f"Running {task}", args.progress)
    return monotonic()


def save_run(task, args, payload, report, started):
    if task == "bat_calibration":
        output = Path(args.out_dir) / args.json_name
        report_path = Path(args.out_dir) / args.md_name
    else:
        output, report_path = Path(args.out), Path(args.report)
    folder = output.parent
    folder.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    gallery = folder / ("index.html" if output.name == "results.json" else output.stem + ".html")
    # An interrupted or data-only rerun must not advertise the previous run's figures.
    gallery.unlink(missing_ok=True)
    payload["config"] = resolved_config(args)
    status("  Saving results...", args.progress)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    if args.plots:
        from src.plots import render_plots
        status("  Drawing plots...", args.progress)
        stems = render_plots(task, payload, folder)
        # Build links from this run's exact outputs, not a glob that includes stale plots.
        def link(path):
            return html.escape(quote(os.path.relpath(path, folder)), quote=True)
        title = task.replace("_", " ").title()
        note = ("Public BAT proxy calibration; this is not deployment lift." if task == "bat_calibration"
                else "Controlled synthetic evidence; this is not public-BAT deployment lift.")
        images = "\n".join(
            f'<figure><img src="{link(folder / (stem + ".png"))}" alt="{stem.replace("_", " ")}">'
            f'<figcaption><a href="{link(folder / (stem + ".pdf"))}">Download PDF</a> · '
            f'<a href="{link(folder / (stem + ".png"))}">Download PNG</a></figcaption></figure>'
            for stem in stems
        )
        settings = html.escape(json.dumps(payload["config"], indent=2))
        gallery.write_text(f'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{title}</title>
<style>body{{font:16px system-ui;max-width:1000px;margin:40px auto;padding:0 20px;color:#243247}}
img{{width:100%;height:auto}}figure{{margin:30px 0}}a{{color:#24659b}}pre{{overflow:auto;background:#f3f5f7;padding:16px}}</style>
<h1>{title}</h1><p>{note}</p>
<p><a href="{link(output)}">Result data</a> · <a href="{link(report_path)}">Detailed report</a></p>
{images}<details><summary>Parameters used for this run</summary><pre>{settings}</pre></details></html>
''', encoding="utf-8")
        print(f"Done in {monotonic() - started:.1f}s. Open {gallery}", flush=True)
    else:
        print(f"Done in {monotonic() - started:.1f}s. Results: {output}", flush=True)
    return 0
