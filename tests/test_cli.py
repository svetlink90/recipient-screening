import io
import sys

from recipient_screening.cli import main

from helpers import CLEAN_EVM, SANCTIONED_EVM, make_config


def test_cli_exit_code_clear(tmp_path, capsys):
    cfg = make_config(tmp_path)
    code = main(["--config", str(cfg), "screen", CLEAN_EVM,
                 "--entity", "Harmless Counterparty Ltd"])
    assert code == 0
    assert "VERDICT: CLEAR" in capsys.readouterr().out


def test_cli_exit_code_stop_hit(tmp_path, capsys):
    cfg = make_config(tmp_path)
    code = main(["--config", str(cfg), "screen", SANCTIONED_EVM])
    assert code == 2
    out = capsys.readouterr().out
    assert "VERDICT: STOP_HIT" in out
    assert "REPORT_MD:" in out  # report path printed for the relaying human


def test_cli_check_lists(tmp_path, capsys):
    cfg = make_config(tmp_path)
    main(["--config", str(cfg), "update"])
    capsys.readouterr()
    code = main(["--config", str(cfg), "check-lists"])
    assert code == 0
    out = capsys.readouterr().out
    assert "ofac_sdn" in out and "FRESH" in out
