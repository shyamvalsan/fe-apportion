# fe-apportion

**Every unit accounted for, with caps and an inspectable rounding decision.**

Three teams share 100 compute credits in the ratio 8:1:1, but the first team can consume only 40. Simple proportional division leaves work to the caller: what happens to the extra 40 credits, and who receives indivisible remainders? `fe-apportion` redistributes capacity first, then allocates every integer unit. The result is **40, 30, 30**, with a record of which cap bound and which recipients received a rounding unit.

This is a small, dependency-free Fe library for quota planning, capped shared-cost calculations, and other bounded allocation problems. The same implementation runs in Fe's local EVM simulator and as native code. The included EVM adapter only calculates; it has no storage, transfers, external calls, or deployment requirement.

The algorithm is weighted water filling followed by Hamilton/largest-remainder rounding. These are established methods. The contribution is a reusable Fe implementation with explicit bounds, audit metadata, examples, and independent exact-rational tests—not a new allocation theorem.

## Quick demo

Use the official **Fe 26.5.0**, reporting `fe 26.5.0 (3dab95f)`. Native executables require Linux x86_64 or macOS AArch64; Windows can run the EVM checks. Python 3.10+ is used only for verification, not by the library or native executable.

```sh
fe test
fe test examples/evm
fe build examples/native --backend native --emit executable
printf '100 0 8:40 1:100 1:100\n' | examples/native/out/apportion_cli
```

Expected demo output:

```json
{"shares":["40","30","30"],"rounded_up":[false,false,false],"saturated":[true,false,false],"remainders":["0","0","0"],"rounding_denominator":"2"}
```

A rounding example:

```sh
printf '10 2 1 1 1\n' | examples/native/out/apportion_cli
```

This returns shares `["3","3","4"]`. All three remainders are `1/3`; the caller selected index 2 as the first tie position.

Installation instructions and official release links: [Fe installation](https://fe-lang.org/getting-started/installation/) and [v26.5.0 release](https://github.com/argotorg/fe/releases/tag/v26.5.0). The checked-in CI downloads the Linux binary directly and verifies its SHA-256; it does not execute a remote installer. Compiler binaries are not included in this repository.

## Use the library

Add a local dependency in the consuming ingot's `fe.toml`:

```toml
[dependencies]
apportion = "../fe-apportion"
```

```fe
use apportion::{allocate_capped, AllocationError, TieBreak}

let result = allocate_capped(
    100,
    [8, 1, 1],
    [40, 100, 100],
    TieBreak::Index,
)
match result {
    Result::Ok(allocation) => {
        assert!(allocation.shares[0] == 40)
    }
    Result::Err(AllocationError::NoPositiveWeight) => panic()
    Result::Err(AllocationError::InsufficientCapacity) => panic()
}
```

The public functions are `allocate(total, weights, tie_break)` and `allocate_capped(total, weights, caps, tie_break)`. The first supplies an implicit cap of `total` for every recipient. Fe infers the const-generic array length. `where N > 0 && N <= 64` rejects unsupported lengths at compile time. All weights, caps, totals and shares are `u128`; intermediate arithmetic and remainder metadata use `u256`.

Fe's `Result` parameters are error-first: `Result<AllocationError, Allocation<N>>`. Match errors explicitly as in the examples. There are no hidden retries, logs, storage changes, or allocations of funds.

## Defined behavior

- A zero total succeeds with zero shares and zero metadata, including when all weights are zero.
- For a positive total, no positive weight returns `NoPositiveWeight`. Otherwise, insufficient total capacity among positive-weight recipients returns `InsufficientCapacity`.
- A zero weight excludes a recipient. Its cap cannot make an otherwise infeasible allocation feasible.
- Fe returns a complete allocation or an error; there is no partial success.
- Caps bind against the continuous weighted allocation. Excess is redistributed among the remaining eligible recipients before integer rounding.
- `TieBreak::Index` chooses the lowest input index on equal remainders. `Rotate(k)` scans cyclically from `k % N`. It is a caller-supplied priority, not randomness.

The result exposes:

| Field | Meaning |
| --- | --- |
| `shares` | Final integer allocation; its sum equals `total` on success. |
| `bonuses` | `true` if the final largest-remainder stage added one unit to that recipient's floor quota. Native JSON calls this `rounded_up`. |
| `saturated` | `true` if a recipient was frozen at a binding cap **before** rounding. A rounding bonus can bring another recipient exactly to its cap while this flag remains `false`. |
| `remainders` | Numerators of the fractional residual quotas in the last stage; zero for excluded or already-frozen recipients. |
| `rounding_denominator` | Sum of active weights in the residual-quota stage. Zero means that stage was skipped because the total was zero or the entire budget was frozen at caps. It can be nonzero even when all remainders are zero. This is not a reduced-fraction denominator. |

Given a nonzero denominator, a non-frozen recipient's exact residual quota is `shares[i] - (bonuses[i] ? 1 : 0) + remainders[i] / rounding_denominator`. Use the original ordered inputs with the report to reproduce a decision.

## Native input and EVM adapter

The native program reads **one allocation from standard input through EOF**:

```text
TOTAL TIE_START WEIGHT[:CAP] WEIGHT[:CAP] ...
```

There must be 1–64 recipients. Decimal integers are unsigned and limited to `u128`. A missing cap defaults to the total. Separators are ASCII space, tab, CR, and LF. Signs, fractions, hex, non-ASCII bytes, multiple colons, overflowing numbers, and tokens longer than 80 bytes are rejected. Leading zeroes are accepted within that token limit. The tie start is reduced modulo the actual recipient count before the fixed-size native adapter calls the library. Input is processed once; this is not a streaming service. The underlying standard I/O capability treats read errors as end-of-input.

Success is one JSON object and exit code 0. Errors are `{"error":"..."}` and exit code 2. Integer values are JSON strings to preserve all 128/256 bits in consumers that use floating-point numbers. No output files are created by the executable.

`examples/evm` exposes `preview(uint128,uint128[8],uint128[8],uint8)`. It returns `(status, shares, bonuses, saturated, remainders, denominator)`, where status is 0 for success, 1 for no positive weight, and 2 for insufficient capacity. Pad unused slots with zero weights and caps; its tie rotation is modulo **eight slots**, so choose the desired populated starting slot explicitly. `fe test examples/evm` deploys and calls this adapter inside the local test simulator. No account, node, wallet, chain transaction, or funds are needed.

## Reproduce verification

```sh
python3 tools/verify.py --native
```

Use `--fe /path/to/fe` for a compiler outside PATH. Omit `--native` on Windows. The runner checks formatting, all 151 exact-rational fixtures and nine hand-written library tests on the EVM, three adapter tests, adapter compilation, and compile-time rejection of N=0 and N=65. With `--native`, it also runs the 160 library tests natively, builds the executable, compares 1,023 executable outputs with the independent Fraction oracle, and runs 249 parser/report checks. Logs are written to `.verify/`.

The oracle uses Python unbounded integers and exact `Fraction` cap/weight breakpoints, rather than reproducing the Fe implementation's repeated cap-freezing loop. Fixtures include maximum `u128` products, 64 large weights, zero eligibility, successive caps, insufficient capacity, tie rotation, and Hamilton counterexamples. Expected data is committed in `tests/vectors.json`; `tools/oracle.py --check-generated` checks it. To change fixtures intentionally, run `python3 tools/oracle.py --generate`, then `fe fmt src`.

See [VALIDATION.md](VALIDATION.md) for the observed environment and [DESIGN.md](DESIGN.md) for arithmetic bounds and reasoning. Tests and review provide evidence, not a formal verification or an independent production audit.

## Limits and incentive caveats

The algorithm uses O(N²) time and O(N) fixed-size working arrays, with N capped at 64; the number of loops does not scale with the size of the total. No EVM gas guarantee is made. Adapters should set a gas budget appropriate to their environment.

Hamilton rounding is **not house-monotone**. For weights `[1500,1500,900,500,500,200]`, total 25 gives `[7,7,4,3,3,1]`, while total 26 gives `[8,8,5,2,2,1]`: increasing the total reduces two recipients' shares. Both outcomes are tested. It also has population and new-recipient paradoxes. This package does not promise every notion of fairness.

Identity splitting can benefit a participant: total 2 with weights `[2,1,1]` gives `[1,1,0]`; splitting the first recipient into two adjacent weight-1 identities gives `[1,1,0,0]`, increasing its combined share from 1 to 2. Ordering and selecting the tie offset after seeing results can also favor a recipient. Fix the eligible identity set, weights, caps, ordering and tie rule before calculation. The library does not authenticate those inputs or prevent their manipulation.

This is a calculation library. It does not enforce who controls weights, implement financial custody, or establish that a chosen allocation policy is appropriate for a particular organization.

## Fe-specific contribution, provenance, and AI disclosure

The core contribution uses Fe const-generic array lengths and compile-time predicates to bound arithmetic and work; `u128`/`u256` operations compile through both backends; typed errors make infeasibility explicit. Native reading/writing is isolated behind Fe `Read`/`Write` effects. The EVM adapter translates the same pure result to a fixed ABI without adding state.

All project code and documentation were produced for this entry with substantial OpenAI Codex agent assistance, including implementation, test generation, review, and documentation. The independent reference and review were also AI-assisted. Executed tests are distinguished from reasoning in the validation record. Automated testing and AI-assisted review are not an independent human audit. The responsible entrant remains accountable for understanding and explaining the work.

No third-party application source or template contract was copied into the project. Fe language/library API patterns were learned from its official documentation, standard library source, and official starter's local-test example. Those tools and references remain their authors' work. The project has no third-party runtime dependency outside Fe core/std. Original project files are provided under the [MIT license](LICENSE).
