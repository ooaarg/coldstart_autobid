"""Shared YAML defaults and argparse validation for the three main experiments."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import yaml


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"
TASKS = ("warm_start", "supported_bridge", "bat_calibration")
COMMON = ("output_dir", "plots", "progress")


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise ValueError("must be a positive integer")
    return number


def nonnegative_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("must be finite and nonnegative")
    return number


def positive_float(value: str) -> float:
    number = nonnegative_float(value)
    if number == 0:
        raise ValueError("must be positive")
    return number


def controller_gain(value: str) -> float:
    number = positive_float(value)
    if number >= 2:
        raise ValueError("must be less than 2 for a stable residual controller")
    return number


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    """A custom file may override any subset of the checked-in paper defaults."""
    def read(source: Path) -> dict:
        with source.open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
        if not isinstance(data, dict):
            raise ValueError(f"{source}: expected a YAML mapping")
        unknown = data.keys() - {*TASKS, *COMMON, "tasks"}
        if unknown:
            raise ValueError(f"{source}: unknown sections: {', '.join(map(str, unknown))}")
        for task in TASKS:
            if task in data and not isinstance(data[task], dict):
                raise ValueError(f"{source}: {task} must be a mapping")
        return data

    config = read(DEFAULT_CONFIG)
    path = Path(path).resolve()
    if path != DEFAULT_CONFIG.resolve():
        overrides = read(path)
        for task in TASKS:
            config[task].update(overrides.get(task, {}))
        for key in ("tasks", *COMMON):
            if key in overrides:
                config[key] = overrides[key]
    tasks = config.get("tasks")
    if not isinstance(tasks, list) or not tasks or any(task not in TASKS for task in tasks):
        raise ValueError(f"tasks must be a nonempty list drawn from {', '.join(TASKS)}")
    if len(set(tasks)) != len(tasks):
        raise ValueError("tasks must not contain duplicates")
    return config


def add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-dir", default=argparse.SUPPRESS, help="Parent folder for task outputs")
    parser.add_argument("--plots", action=argparse.BooleanOptionalAction, default=argparse.SUPPRESS,
                        help="Save plots and an HTML gallery after each experiment")
    parser.add_argument("--progress", action=argparse.BooleanOptionalAction, default=argparse.SUPPRESS,
                        help="Show stage messages and terminal progress bars")


def configure_parser(parser: argparse.ArgumentParser, task: str, path: str | Path) -> None:
    """Use the argparse options as the schema for YAML values."""
    parser.formatter_class = argparse.ArgumentDefaultsHelpFormatter
    parser.add_argument("--config", default=str(path), help="YAML configuration file")
    parser.add_argument("--print-config", action="store_true", default=argparse.SUPPRESS,
                        help="Show resolved settings without running")
    add_output_options(parser)
    try:
        config = load_config(path)
        defaults = {**config[task], **{key: config[key] for key in COMMON}}
        actions = {action.dest: action for action in parser._actions if action.dest not in {"help", "config", "print_config"}}
        unknown = defaults.keys() - actions.keys()
        if unknown:
            raise ValueError(f"{task}: unknown settings: {', '.join(map(str, unknown))}")
        # argparse validates CLI values, but set_defaults alone does not validate YAML.
        for key, value in defaults.items():
            action = actions[key]
            if value is None:
                if key not in {"max_rows", "campaign_max_rows", "vcg_stats", "vcg_campaigns", "fpa_stats", "fpa_campaigns"}:
                    raise ValueError(f"{task}.{key} cannot be null")
                continue
            if isinstance(action, argparse.BooleanOptionalAction):
                if type(value) is not bool:
                    raise ValueError(f"{task}.{key} must be true or false")
                continue
            values = value if action.nargs == "+" else [value]
            if not isinstance(values, list) or not values:
                raise ValueError(f"{task}.{key} must be a nonempty list")
            for item in values:
                if isinstance(item, (bool, list, dict)):
                    raise ValueError(f"{task}.{key}: invalid value {item!r}")
                if action.type:
                    action.type(str(item))
                elif not isinstance(item, str) or not item.strip():
                    raise ValueError(f"{task}.{key} must be a nonempty string")
                if action.choices and item not in action.choices:
                    raise ValueError(f"{task}.{key} must be one of {action.choices}")
            if action.type:
                defaults[key] = [action.type(str(item)) for item in values] if action.nargs == "+" else action.type(str(value))
        parser.set_defaults(**defaults)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        parser.error(str(exc))


def validate_args(parser: argparse.ArgumentParser, task: str, args: argparse.Namespace) -> None:
    folder = Path(args.output_dir) / task
    if task == "bat_calibration":
        args.out_dir = args.out_dir or str(folder)
        args.json_name = args.json_name or "results.json"
        args.md_name = args.md_name or "report.md"
    else:
        args.out = args.out or str(folder / "results.json")
        args.report = args.report or str(Path(args.out).with_suffix(".md"))
    if task == "supported_bridge" and args.horizons != sorted(set(args.horizons)):
        parser.error("horizons must be strictly increasing with no duplicates")


def config_path(argv: list[str] | None) -> str:
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args, _ = parser.parse_known_args(argv)
    return args.config


def parse_config_args(parser: argparse.ArgumentParser, task: str, argv: list[str] | None) -> argparse.Namespace:
    configure_parser(parser, task, config_path(argv))
    parser.set_defaults(print_config=False)
    args = parser.parse_args(argv)
    validate_args(parser, task, args)
    return args


def resolved_config(args: argparse.Namespace) -> dict:
    return {key: value for key, value in vars(args).items() if key not in {"config", "print_config", "task"}}


def print_config(args: argparse.Namespace) -> None:
    print(json.dumps(resolved_config(args), indent=2))
