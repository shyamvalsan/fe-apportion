#!/usr/bin/env python3
"""Reproduce checks with an already installed official Fe 26.5.0 compiler."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fe", default="fe", help="Path to the Fe 26.5.0 executable")
    parser.add_argument("--native", action="store_true", help="Also run native checks (Linux x86_64 or macOS AArch64)")
    args = parser.parse_args()
    fe = str(Path(args.fe).resolve()) if Path(args.fe).is_file() else args.fe
    logs = ROOT / ".verify"
    logs.mkdir(exist_ok=True)
    records = []

    def run(name, command, expected_error=None):
        start = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=240)
        output = result.stdout + result.stderr
        (logs / f"{name}.log").write_text(output, encoding="utf-8")
        ok = result.returncode == 0 if expected_error is None else (
            result.returncode != 0 and expected_error in output
        )
        records.append({"check": name, "passed": ok, "exit_code": result.returncode,
                        "seconds": round(time.monotonic() - start, 3)})
        (logs / "results.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        print(f"{'PASS' if ok else 'FAIL'} {name}", flush=True)
        if not ok:
            print(output)
            raise SystemExit(1)
        return output

    version = run("compiler-version", [fe, "--version"])
    if not version.startswith("fe 26.5.0 "):
        raise SystemExit(f"Expected Fe 26.5.0; got {version.strip()}")
    run("oracle-fixtures", [sys.executable, "tools/oracle.py", "--check-generated"])
    for path in ["src", "examples/native", "examples/evm", "tests/compile_fail"]:
        run("format-" + path.replace("/", "-"), [fe, "fmt", path, "--check", "--color", "never"])
    run("library-evm", [fe, "test", "--color", "never"])
    run("adapter-evm", [fe, "test", "examples/evm", "--color", "never"])
    run("adapter-build", [fe, "build", "examples/evm", "--emit", "abi,bytecode,runtime-bytecode", "--color", "never"])
    for name in ["zero", "sixty_five"]:
        run("reject-" + name, [fe, "check", "tests/compile_fail/" + name, "--color", "never"],
            "error[8-0093]: const requirement is not satisfied")
    if args.native:
        run("library-native", [fe, "test", "--backend", "native", "--color", "never"])
        run("cli-build", [fe, "build", "examples/native", "--backend", "native", "--emit", "executable", "--color", "never"])
        executable = "examples/native/out/apportion_cli"
        run("cli-oracle", [sys.executable, "tools/oracle.py", "--cli", executable, "--random-cases", "1000"])
        run("cli-input", [sys.executable, "tools/test_cli.py", executable])
    print(f"All {len(records)} checks passed. Logs: .verify/")


if __name__ == "__main__":
    main()
