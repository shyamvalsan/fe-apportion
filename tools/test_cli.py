#!/usr/bin/env python3
"""Native CLI grammar, bounds, metadata and tie-normalization regressions.

Usage: python3 tools/test_cli.py examples/native/out/apportion_cli
Uses only Python's standard library. Run on the binary's native platform.
The larger exact-rational differential suite is in tools/oracle.py.
"""
import argparse
import json
from pathlib import Path
import subprocess

MAX = 2**128 - 1


def output(shares, bonuses, saturated, remainders, denominator):
    return {
        "shares": [str(x) for x in shares],
        "rounded_up": bonuses,
        "saturated": saturated,
        "remainders": [str(x) for x in remainders],
        "rounding_denominator": str(denominator),
    }


def checks():
    errors = [
        ("empty", b"", "MissingTotal"),
        ("whitespace_only", b" \t\r\n", "MissingTotal"),
        ("missing_tie", b"1", "MissingTieStart"),
        ("missing_recipients", b"1 0", "MissingRecipients"),
    ]
    invalid_numbers = [
        b"-1", b"+1", b"1.0", b"0x10", b"1e2", b":", b"1:2", b"abc",
        b"\x00", b"\x1f", b"\x7f", b"\x80", b"\xff", "١".encode(),
        str(MAX + 1).encode(), b"0" * 81,
    ]
    for i, token in enumerate(invalid_numbers):
        errors += [
            (f"invalid_total_{i}", token + b" 0 1", "InvalidTotal"),
            (f"invalid_tie_{i}", b"1 " + token + b" 1", "InvalidTieStart"),
        ]
    invalid_recipients = [
        b":1", b"1:", b":", b"1::2", b"1:2:3", b"-1", b"+1", b"1.0",
        b"1e2", b"1:-1", b"1:+1", b"a:1", b"1:a", str(MAX + 1).encode(),
        b"1:" + str(MAX + 1).encode(), b"0" * 81, b"1:" + b"0" * 79,
        b"\x00", b"\x0b", b"\x0c", b"\xff",
    ]
    for i, token in enumerate(invalid_recipients):
        errors.append((f"invalid_recipient_{i}", b"1 0 " + token, "InvalidRecipient"))
    errors += [
        ("too_many", b"1 0 " + b"1 " * 65, "TooManyRecipients"),
        ("too_many_zero_total", b"0 0 " + b"0 " * 65, "TooManyRecipients"),
        ("no_positive_weight", b"1 0 0:100", "NoPositiveWeight"),
        ("excluded_capacity", b"3 0 1:2 0:100", "InsufficientCapacity"),
        ("zero_capacity", b"1 0 1:0", "InsufficientCapacity"),
    ]
    for name, payload, error in errors:
        yield name, payload, 2, {"error": error}

    # Hand-computed cases cover all metadata, including early returns.
    q = MAX // 2
    valid = [
        ("equal", b"10 0 1 1 1", output([4, 3, 3], [True, False, False], [False] * 3, [1] * 3, 3)),
        ("max_product", f"{MAX} {MAX} {MAX}:{MAX} {MAX}:{MAX}".encode(), output([q, q + 1], [False, True], [False] * 2, [MAX] * 2, 2 * MAX)),
        ("longest_canonical_recipient", f"{MAX} 0 {MAX}:{MAX}".encode(), output([MAX], [False], [True], [0], 0)),
        ("leading_zeros_80", b"0" * 80 + b" " + b"0" * 80 + b" " + b"0" * 80, output([0], [False], [False], [0], 0)),
        ("recipient_token_80", b"1 0 " + b"0" * 77 + b"1:1", output([1], [False], [True], [0], 0)),
        ("separators", b"\r\n\t 10\t2\r1\n1\t1\r\n", output([3, 3, 4], [False, False, True], [False] * 3, [1] * 3, 3)),
        ("all_caps_frozen", b"6 0 1:1 2:2 3:3", output([1, 2, 3], [False] * 3, [True] * 3, [0] * 3, 0)),
        ("integral_residual_quotas", b"6 0 1:100 2:100", output([2, 4], [False] * 2, [False] * 2, [0] * 2, 3)),
        ("rounding_hits_cap", b"1 0 1:1 1:2", output([1, 0], [True, False], [False] * 2, [1] * 2, 2)),
        ("zero_total", f"0 0 0:0 1:{MAX}".encode(), output([0] * 2, [False] * 2, [False] * 2, [0] * 2, 0)),
    ]
    for name, payload, expected in valid:
        yield name, payload, 0, expected

    # One indivisible unit with equal positive weights has a direct answer:
    # the first positive recipient in the cyclic order receives it. This checks
    # normalization by actual recipient count, despite the CLI's 64-slot array.
    for n in (1, 2, 3, 5, 7, 8, 16, 31, 32, 63, 64):
        for rotate in (0, 1, n - 1, n, 63, 64, 65, MAX):
            for sparse in (False, True):
                weights = [int(not sparse or i % 3 == 1 or i == n - 1) for i in range(n)]
                positive = sum(weights)
                start = rotate % n
                winner = next((start + k) % n for k in range(n) if weights[(start + k) % n])
                shares = [int(i == winner) for i in range(n)]
                saturated = [bool(w and positive == 1) for w in weights]
                bonuses = [bool(i == winner and positive > 1) for i in range(n)]
                remainders = weights if positive > 1 else [0] * n
                denominator = positive if positive > 1 else 0
                payload = (" ".join(["1", str(rotate)] + [str(w) for w in weights]) + "\n").encode()
                yield f"rotation_{n}_{rotate}_{sparse}", payload, 0, output(shares, bonuses, saturated, remainders, denominator)

    # Both the common denominator and every remainder exceed u128 here.
    q, units = divmod(MAX, 64)
    awarded = {(63 + j) % 64 for j in range(units)}
    expected = output([q + int(i in awarded) for i in range(64)], [i in awarded for i in range(64)], [False] * 64, [units * MAX] * 64, 64 * MAX)
    payload = (f"{MAX} 63 " + " ".join([str(MAX)] * 64)).encode()
    yield "64_recipients_u256_metadata", payload, 0, expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    binary = args.executable.resolve()
    count = errors = 0
    for name, payload, expected_code, expected in checks():
        proc = subprocess.run([str(binary)], input=payload, capture_output=True, timeout=5)
        try:
            actual = json.loads(proc.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AssertionError((name, proc.returncode, proc.stdout, proc.stderr)) from exc
        if proc.returncode != expected_code or actual != expected or proc.stderr:
            raise AssertionError((name, proc.returncode, actual, proc.stderr, expected_code, expected))
        count += 1
        errors += expected_code != 0
    print(f"Native CLI: {count} grammar/bounds/metadata/tie checks passed ({errors} expected errors, {count-errors} valid inputs).")


if __name__ == "__main__":
    main()
