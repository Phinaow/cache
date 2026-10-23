"""Check routed timing, CDC, DRC, mailbox skew and bitstream artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def timing_metrics(text):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if "WNS(ns)" not in line:
            continue
        values = lines[index + 2].split()
        if len(values) < 12:
            raise ValueError("Incomplete timing summary")
        result = {
            "setup_slack_ns": float(values[0]),
            "hold_slack_ns": float(values[4]),
            "pulse_width_slack_ns": float(values[8]),
            "setup_failures": int(values[2]),
            "hold_failures": int(values[6]),
            "pulse_width_failures": int(values[10]),
        }
        if any(result[key] < 0 for key in ("setup_slack_ns", "hold_slack_ns", "pulse_width_slack_ns")):
            raise ValueError(f"Negative timing slack: {result}")
        if any(result[key] for key in ("setup_failures", "hold_failures", "pulse_width_failures")):
            raise ValueError(f"Failing timing endpoints: {result}")
        return result
    raise ValueError("Timing summary missing")


def check_cdc(text):
    if "CDC Report" not in text:
        raise ValueError("CDC report missing")
    critical = re.findall(r"^(CDC-\d+)\s+(?:Critical|Error)\s+(\d+)\s", text, re.MULTILINE)
    if any(int(count) for _, count in critical):
        raise ValueError(f"Critical CDC findings: {critical}")
    return re.findall(r"^(CDC-\d+)\s+Warning\s+(\d+)\s", text, re.MULTILINE)


def check_drc(text):
    if "Report DRC" not in text:
        raise ValueError("DRC report missing")
    critical = re.findall(r"^\|\s*(\S+)\s*\|\s*(?:Error|Critical Warning)\s*\|", text, re.MULTILINE)
    if critical:
        raise ValueError(f"Critical DRC findings: {critical}")
    return re.findall(r"^\|\s*(\S+)\s*\|\s*Warning\s*\|", text, re.MULTILINE)


def skew_slacks(text):
    values = re.findall(r"^\s*(?:Slow|Fast)\s+[\d.]+\s+[\d.]+\s+(-?[\d.]+)\s*$", text, re.MULTILINE)
    if len(values) < 2:
        raise ValueError("Both mailbox skew constraints must be reported")
    slacks = [float(value) for value in values]
    if min(slacks) < 0:
        raise ValueError(f"Mailbox skew failure: {slacks}")
    return slacks


def inspect_reports(directory):
    directory = Path(directory)
    result = timing_metrics((directory / "timing.rpt").read_text())
    result["cdc_warnings"] = check_cdc((directory / "cdc_routed.rpt").read_text())
    result["drc_warnings"] = check_drc((directory / "drc_routed.rpt").read_text())
    result["mailbox_skew_slacks_ns"] = skew_slacks((directory / "bus_skew.rpt").read_text())
    bitstream = directory / "cache_fpga.runs" / "impl_1" / "uart_to_cache.bit"
    if bitstream.stat().st_size < 1024:
        raise ValueError("Bitstream is empty or truncated")
    result["bitstream"] = str(bitstream)
    result["sha256"] = hashlib.sha256(bitstream.read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directories", nargs="+", type=Path)
    arguments = parser.parse_args()
    results = {str(directory): inspect_reports(directory) for directory in arguments.directories}
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
