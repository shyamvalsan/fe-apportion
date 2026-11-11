# Observed validation

Recorded November 10, 2026, at approximately 22:25 UTC. These are executed local results, not a claim that hosted CI or a contest judge has accepted the project.

## Compiler and environment

- Official Fe **26.5.0 (3dab95f)** Linux x86_64 binary.
- Download: `https://github.com/argotorg/fe/releases/download/v26.5.0/fe_linux_amd64`
- SHA-256: `3732fbe8a6e9d2ea3925d02d0e3a1478bc1e01d742c2be75d3ea7300c46c45f0`.
- Ubuntu under WSL, x86_64, Python **3.12.14**. Because the host distribution's libc was older than the compiler requires, the compiler was launched using an isolated workspace extraction of the official Ubuntu libc6 2.39 package. No system library was replaced. The resulting native executable ran directly on the host.
- CI is configured for Ubuntu 24.04 with the same pinned compiler download and checksum. Hosted CI results are not part of this recorded local run; subsequent workflow results should be assessed separately.
- The official Windows binary (SHA-256 `d86ca3c6fdadeb8335f7033e3a68fdb7d2aab4eafd22c1e23bec047d2a8b2674`) was also used during development; the complete final run below used the Linux binary for both backends.

## Complete final verification

`python3 tools/verify.py --fe <official-compiler-launcher> --native` completed all **15 stages** successfully. All commands used optimization defaults (level 1). Compiler checks, formatting, and error expectations are part of the runner.

| Check | Observed result |
| --- | --- |
| Oracle fixture consistency | 151 committed fixtures match independently calculated exact-rational expectations. |
| Library, EVM simulator | 160 passed; 0 failed. |
| Library, native backend | 160 passed; 0 failed. |
| Local EVM adapter calls | 3 passed; 0 failed. |
| EVM adapter build | ABI, creation bytecode and runtime bytecode produced; ABI marks `preview` as `pure`. |
| N=0 and N=65 | Both rejected with `error[8-0093]: const requirement is not satisfied`. |
| Compiled native executable vs Fraction oracle | 1,023 cases passed; seed `0xfea110ca`. |
| Compiled native input/report tests | 249 passed: 62 expected errors, 187 valid inputs; checks include full JSON fields and exit status. |
| Formatting | Library, both examples, and deliberate compile-fail fixtures pass. |

The EVM adapter runtime bytecode is 6,447 bytes; creation bytecode is 6,467 bytes for this build. No reliable per-call gas report was collected, so this entry makes no measured gas claim. The 1,000,000 gas allowance in adapter tests is a test setting, not a gas measurement or recommended production limit.

Portable copies of the complete run logs and stage timings are in `validation/`. Local absolute project paths were replaced with `<project>` in those copies; test output was otherwise retained. Timings are environment-specific and are not benchmarks.

## Review scope

A second AI-assisted reviewer read the arithmetic and metadata behavior and found no defect in its independent model comparisons. The review used a subset-enumerated exact-rational solution, with 82,488 exhaustive small cases and 1,500 full-width random cases, plus a 64-recipient maximum-weight case. This supplementary check tests a transcription of the algorithm; it is distinct from the actual compiled Fe and executable tests above. It does not constitute formal verification or human sign-off.

The native parser was independently reviewed and checked on its compiled executable, including full-width tie starts, actual-recipient-count normalization despite 64-slot padding, malformed bytes, overflow, long tokens, and excess recipients. Those checks are now reproducible in `tools/test_cli.py`.

These checks used local execution and simulated EVM deployment; no network deployment or funds transfer was involved. This record covers observed software behavior and does not assert human audit, contest acceptance, judging outcomes, or payment.
