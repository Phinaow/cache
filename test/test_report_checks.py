"""Fault injection verifies that physical-report checks cannot silently pass."""
import pytest

from scripts.check_fpga_reports import timing_metrics, check_cdc, check_drc, skew_slacks


TIMING = "WNS(ns) TNS(ns) Fail Total WHS(ns) THS(ns) Fail Total WPWS(ns) TPWS(ns) Fail Total\n---\n0.7 0 0 100 0.01 0 0 100 0 0 0 100\n"


def test_timing_checker_rejects_negative_slack_and_missing_data():
    assert timing_metrics(TIMING)["setup_slack_ns"] == 0.7
    for broken in ("", TIMING.replace("0.7", "-0.1"), TIMING.replace("0.01", "-0.01"),
                   TIMING.replace("0 0 100", "0 1 100", 1)):
        with pytest.raises(ValueError):
            timing_metrics(broken)


def test_cdc_and_drc_checkers_reject_critical_findings():
    assert check_cdc("CDC Report\nCDC-8 Warning 2 Vendor reset\n") == [("CDC-8", "2")]
    assert check_drc("Report DRC\n| RBOR-1 | Warning | Output register |\n") == ["RBOR-1"]
    with pytest.raises(ValueError):
        check_cdc("CDC Report\nCDC-1 Critical 1 Unsafe transfer\n")
    with pytest.raises(ValueError):
        check_drc("Report DRC\n| UCIO-1 | Error | Unconstrained port |\n")


def test_skew_checker_requires_both_mailboxes_and_nonnegative_slack():
    report = "Slow 10.000 1.000 9.000\nSlow 10.000 0.500 9.500\n"
    assert skew_slacks(report) == [9.0, 9.5]
    for broken in ("", "Slow 10.000 1.000 9.000\n", report.replace("9.000", "-0.100")):
        with pytest.raises(ValueError):
            skew_slacks(broken)
