"""Configuration, command-line precedence, and offline end-to-end checks."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from experiments.__main__ import main
from src import bat_runner, run_supported_bridge as bridge, run_warm_start_suite as warm
from src.config import DEFAULT_CONFIG, load_config


ROOT = Path(__file__).resolve().parents[1]


def write_config(tmp_path, data):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


def test_paper_defaults_and_cli_overrides(tmp_path):
    assert warm.parse_args([]).seeds == 100
    assert bridge.parse_args([]).horizons == [1, 3, 6, 12, 24]
    assert bat_runner.parse_args([]).full is True
    path = write_config(tmp_path, {"warm_start": {"seeds": 2, "gain": 0.4}})
    args = warm.parse_args(["--config", path, "--seeds", "3"])
    assert (args.seeds, args.gain, args.horizon) == (3, 0.4, 100)
    # Reading a custom config must not mutate defaults for subsequent runs.
    assert warm.parse_args([]).gain == 0.22


def test_boolean_overrides_and_bat_row_caps(tmp_path):
    path = write_config(tmp_path, {
        "supported_bridge": {"sensitivity": False},
        "bat_calibration": {"full": False, "sample_rows": 7},
    })
    assert bridge.parse_args(["--config", path, "--sensitivity"]).sensitivity is True
    assert bridge.parse_args(["--no-sensitivity"]).sensitivity is False
    assert bat_runner.row_limit(bat_runner.parse_args(["--config", path])) == 7
    assert bat_runner.row_limit(bat_runner.parse_args(["--max-rows", "11"])) == 11
    assert bat_runner.row_limit(bat_runner.parse_args(["--config", path, "--full"])) is None


@pytest.mark.parametrize("data", [
    {"plots": "false"},
    {"progress": 1},
    {"output_dir": None},
    {"warm_start": {"seedz": 2}},
    {"warm_start": {"seeds": 0}},
    {"warm_start": {"seeds": True}},
    {"warm_start": {"seeds": 1.5}},
    {"warm_start": {"horizon": None}},
    {"warm_start": {"gain": 2.0}},
    {"warm_start": {"tolerance": float("nan")}},
    {"warm_start": {"out": 42}},
    {"supported_bridge": {"horizons": [3, 1]}},
    {"supported_bridge": {"horizons": [1, 1]}},
    {"supported_bridge": {"sensitivity_grid": []}},
    {"supported_bridge": {"bootstrap_resamples": -1}},
    {"supported_bridge": {"sensitivity": "false"}},
    {"bat_calibration": {"only": "unknown"}},
    {"bat_calibration": {"max_rows": 0}},
    {"tasks": ["unknown"]},
    {"tasks": ["warm_start", "warm_start"]},
    {"tasks": []},
    {"warm_starts": {}},
    {"warm_start": []},
])
def test_invalid_config_fails_before_running(tmp_path, data, capsys):
    with pytest.raises(SystemExit) as error:
        main(["--config", write_config(tmp_path, data)])
    assert error.value.code == 2
    assert "Running " not in capsys.readouterr().out


@pytest.mark.parametrize("text", ["", "[1, 2]", "warm_start: [", "!!python/object:os.system {}"])
def test_malformed_yaml_is_an_argparse_error(tmp_path, text):
    path = tmp_path / "bad.yaml"
    path.write_text(text)
    with pytest.raises(SystemExit) as error:
        warm.parse_args(["--config", str(path)])
    assert error.value.code == 2


def test_missing_config_is_an_argparse_error(tmp_path):
    with pytest.raises(SystemExit) as error:
        warm.parse_args(["--config", str(tmp_path / "missing.yaml")])
    assert error.value.code == 2


def test_cli_values_are_validated():
    with pytest.raises(SystemExit) as error:
        warm.parse_args(["--seeds", "0"])
    assert error.value.code == 2


@pytest.mark.parametrize("args", [
    ["warm_start", "--print-config"],
    ["--print-config"],
])
def test_preview_runs_nothing(tmp_path, args, capsys):
    path = write_config(tmp_path, {"tasks": ["warm_start"], "warm_start": {"seeds": 2}})
    assert main(["--config", path, *args]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tasks"] == ["warm_start"]
    assert payload["warm_start"]["seeds"] == 2


def test_all_tasks_from_one_yaml_offline(tmp_path):
    campaigns = tmp_path / "campaigns.csv"
    campaigns.write_text("campaign_id,item_id,logical_category\n1,1,category\n")
    stats = tmp_path / "stats.csv"
    with stats.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=bat_runner.REQUIRED_STATS_COLUMNS)
        writer.writeheader()
        for i in range(30):
            writer.writerow(dict(zip(bat_runner.REQUIRED_STATS_COLUMNS,
                                     [1, 1, i * 3600, 2 + i % 3, 1, 0.2, 0.1,
                                      0.01 + i * 0.001, 0.02 + i * 0.001, 0.1, 10])))
    path = write_config(tmp_path, {
        "tasks": ["warm_start", "supported_bridge", "bat_calibration"],
        "warm_start": {"seeds": 1, "horizon": 5, "out": str(tmp_path / "warm.json"), "report": str(tmp_path / "warm.md")},
        "supported_bridge": {"seeds": 1, "contexts": 3, "horizons": [1, 2, 4],
                             "gain": 0.4, "tolerance": 0.02, "guard_z": 1.0, "shrinkage": 50.0,
                             "bootstrap_seed": 17, "bootstrap_resamples": 20, "sensitivity_grid": [0.9, 1.1],
                             "out": str(tmp_path / "bridge.json"), "report": str(tmp_path / "nested" / "bridge.md")},
        "bat_calibration": {"vcg_stats": str(stats), "fpa_stats": str(stats),
                            "vcg_campaigns": str(campaigns), "fpa_campaigns": str(campaigns),
                            "min_category_rows": 2, "max_rows": 20, "out_dir": str(tmp_path / "bat")},
    })
    result = subprocess.run([sys.executable, "-m", "experiments", "--config", path],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert [line for line in result.stdout.splitlines() if line.startswith("Running")] == [
        "Running warm_start", "Running supported_bridge", "Running bat_calibration"]
    payload = json.loads((tmp_path / "bridge.json").read_text())
    expected = bridge.run_bridge(1, 3, payload["seed"], settings=bridge.Settings((1, 2, 4), 0.4, 0.02, 1.0, 50.0, 17, 20))
    assert payload["runs"] == expected["runs"]
    assert payload["gate_status"] == expected["gate_status"]
    assert len(payload["sensitivity"]["rows"]) == 4
    assert payload["config"]["bootstrap_resamples"] == 20
    for path in [tmp_path / "warm.html", tmp_path / "bridge.html", tmp_path / "bat" / "index.html"]:
        assert path.exists()
    for path in [tmp_path / "warm_start_effect_forest.png", tmp_path / "supported_bridge_comparison.png",
                 tmp_path / "supported_bridge_sensitivity.png", tmp_path / "bat" / "bat_selected_category_hour_dual_surfaces_clean.png"]:
        assert path.read_bytes().startswith(b"\x89PNG")
        assert path.with_suffix(".pdf").read_bytes().startswith(b"%PDF")
    assert "Drawing plots" in result.stdout
    assert "Reading local CSV" in result.stdout
    assert "\x1b" not in result.stderr
    bat = json.loads((tmp_path / "bat" / "results.json").read_text())
    assert bat["mode"] == "bounded"
    assert set(bat["auctions"]) == {"vcg", "fpa"}
    for auction in bat["auctions"].values():
        assert auction["rows_seen"] == 20
        assert auction["schema"]["valid"]
        admissible = auction["flat_ols"]["admissible"]
        assert admissible["admissible_beta_v"] > 0
        assert 0 <= admissible["admissible_beta_cpc_mu"] <= 1


def test_main_help_lists_the_three_tasks():
    result = subprocess.run([sys.executable, "-m", "experiments", "--help"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert all(task in result.stdout for task in ["warm_start", "supported_bridge", "bat_calibration"])


def test_default_config_location_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_config()["warm_start"]["seeds"] == 100
    assert Path(warm.parse_args([]).config) == DEFAULT_CONFIG
