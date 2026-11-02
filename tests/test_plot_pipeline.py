"""A changed config must produce changed data and plots in the chosen folder."""

import hashlib
import io
import json
from unittest.mock import patch

import pytest
import yaml

from experiments.__main__ import main
from src import progress
from src.bat_surfaces import CategoryHourSurface, select_categories
from src.experiment_utils import bat_row_from_csv


def test_config_to_plot_with_two_controller_gains(tmp_path, capsys):
    results, pictures = [], []
    for gain in [0.22, 0.6]:
        root = tmp_path / f"gain-{gain}"
        config = tmp_path / "trial.yaml"
        config.write_text(yaml.safe_dump({
            "output_dir": str(root),
            "warm_start": {"seeds": 3, "horizon": 12, "gain": gain, "guard_z": 0.0, "shrinkage": 2.0},
        }))
        assert main(["--config", str(config)]) == 0
        folder = root / "warm_start"
        result = json.loads((folder / "results.json").read_text())
        assert result["config"]["gain"] == gain
        assert result["config"]["out"] == str(folder / "results.json")
        results.append(result["runs"])
        pictures.append(hashlib.sha256((folder / "warm_start_effect_forest.png").read_bytes()).hexdigest())
        gallery = (folder / "index.html").read_text()
        assert "warm_start_effect_forest.png" in gallery
        assert "results.json" in gallery
        assert str(gain) in gallery
        report = (folder / "results.md").read_text()
        assert "exceeds `0.0`" in report
        assert "n/(n+2)" in report
        assert (folder / "warm_start_reward_trajectories.pdf").stat().st_size > 1000
    assert results[0][0]["controller_states"][0] == results[1][0]["controller_states"][0]
    assert results[0][0]["controller_states"][1] != results[1][0]["controller_states"][1]
    assert pictures[0] != pictures[1]
    output = capsys.readouterr().out
    assert output.count("Drawing plots") == 2
    assert output.count("Done in") == 2


@pytest.mark.parametrize("placement", ["before", "after"])
def test_data_only_rerun_with_shared_flags(tmp_path, capsys, placement):
    config = tmp_path / "short.yaml"
    config.write_text("warm_start:\n  seeds: 1\n  horizon: 3\n")
    flags = ["--config", str(config), "--output-dir", str(tmp_path), "--no-plots", "--no-progress"]
    args = flags + ["warm_start"] if placement == "before" else ["warm_start"] + flags
    folder = tmp_path / "warm_start"
    folder.mkdir()
    (folder / "index.html").write_text("Previous run's figures")
    assert main(args) == 0
    data = json.loads((folder / "results.json").read_text())
    assert data["config"]["plots"] is False
    assert not list(folder.glob("*.png"))
    assert not (folder / "index.html").exists()
    assert capsys.readouterr().out.count("\n") == 1  # Only the final destination.


def test_progress_bar_only_for_a_terminal():
    for is_terminal in [False, True]:
        stream = io.StringIO()
        stream.isatty = lambda: is_terminal
        with patch.object(progress.sys, "stderr", stream):
            assert list(progress.track(range(5), "Test seeds", enabled=True)) == list(range(5))
        assert bool(stream.getvalue()) == is_terminal


def test_bat_surface_values_and_single_auction_plot(tmp_path):
    surface = CategoryHourSurface()
    for hour in range(24):
        for ctr, cr, price in [(0.1, 0.2, 2), (0.2, 0.3, 3), (0.3, 0.1, 4)]:
            target = 2 * ctr * cr + 0.3 * price * ctr
            bat = bat_row_from_csv({
                "period": str(hour * 3600), "CTRPredicts": str(ctr), "CRPredicts": str(cr),
                "contact_price_bin": str(price), "AuctionWinBidSurplus": str(10 * target), "AuctionCount": "10",
            })
            surface.add(bat, {"logical_category": "1.1"})
    payload = surface.result(top_categories=1, min_cell_rows=3)
    assert len(select_categories(payload["surface"], "s", 24, 5)) == 1
    assert payload["surface"]["s"][0] == pytest.approx([2.0] * 24)
    assert payload["surface"]["alpha"][0] == pytest.approx([0.3] * 24)
    from src.generate_bat_category_hour_surfaces import plot_selected_surfaces
    plot_selected_surfaces({"fpa": payload}, tmp_path)
    assert (tmp_path / "bat_selected_category_hour_dual_surfaces_clean.png").stat().st_size > 1000
    # A stricter support threshold must mask the same observations.
    masked = surface.result(top_categories=1, min_cell_rows=4)
    assert all(value is None for value in masked["surface"]["s"][0])
    plot_selected_surfaces({"fpa": masked}, tmp_path)


def test_bridge_gallery_does_not_reuse_an_old_sensitivity_plot(tmp_path):
    folder = tmp_path / "supported_bridge"
    folder.mkdir()
    (folder / "supported_bridge_sensitivity.png").write_bytes(b"old plot")
    assert main(["supported_bridge", "--output-dir", str(tmp_path), "--seeds", "1", "--contexts", "2",
                 "--bootstrap-resamples", "10", "--no-sensitivity", "--no-progress"]) == 0
    assert "supported_bridge_sensitivity" not in (folder / "index.html").read_text()
    assert "sensitivity" not in json.loads((folder / "results.json").read_text())
