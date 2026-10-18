"""Run one main experiment, or the tasks selected in config.yaml."""

from __future__ import annotations

import argparse
import json

from src import bat_runner, run_supported_bridge, run_warm_start_suite
from src.config import add_output_options, config_path, configure_parser, load_config, resolved_config, validate_args


RUNNERS = {
    "warm_start": run_warm_start_suite,
    "supported_bridge": run_supported_bridge,
    "bat_calibration": bat_runner,
}


def main(argv: list[str] | None = None) -> int:
    path = config_path(argv)
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--config", default=path, help="YAML configuration file")
    parser.add_argument("--print-config", action="store_true", help="Show settings without running")
    add_output_options(parser)
    shared_parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    add_output_options(shared_parser)
    shared_overrides, _ = shared_parser.parse_known_args(argv)
    parser.set_defaults(task="all")
    commands = parser.add_subparsers(dest="task")
    all_parser = commands.add_parser("all", help="Run the tasks listed in config.yaml")
    all_parser.add_argument("--config", default=argparse.SUPPRESS)
    all_parser.add_argument("--print-config", action="store_true", default=argparse.SUPPRESS)
    add_output_options(all_parser)
    task_parsers = {}
    for task, runner in RUNNERS.items():
        task_parser = runner.build_parser()
        configure_parser(task_parser, task, path)
        validate_args(task_parser, task, task_parser.parse_args([]))
        task_parsers[task] = commands.add_parser(
            task, parents=[task_parser], add_help=False, allow_abbrev=False,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description=task_parser.description, help=runner.__doc__.splitlines()[0],
        )
    args = parser.parse_args(argv)
    jobs = []
    if args.task in RUNNERS:
        vars(args).update(vars(shared_overrides))
        validate_args(task_parsers[args.task], args.task, args)
        jobs.append((args.task, RUNNERS[args.task], args))
    else:
        # All task configs were checked above; validate CLI relationships before any run.
        for task in load_config(path)["tasks"]:
            settings = task_parsers[task].parse_args([])
            vars(settings).update(vars(shared_overrides))
            validate_args(task_parsers[task], task, settings)
            jobs.append((task, RUNNERS[task], settings))
    if args.print_config:
        print(json.dumps({"tasks": [task for task, _, _ in jobs],
                          **{task: resolved_config(settings) for task, _, settings in jobs}}, indent=2))
        return 0
    for task, runner, settings in jobs:
        result = runner.run(settings)
        if result:
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
