# Algorithm and arithmetic reasoning

This document is a review aid, not a machine-checked proof.

## Policy

For eligible recipients (positive weights), first solve a continuous weighted allocation of a total T under integer caps: `q_i = min(cap_i, lambda * weight_i)`, choosing a level lambda whose quotas sum to T. Then floor the quotas and award the remaining integer units in descending order of fractional remainder, resolving equal remainders by the declared cyclic index order. Ineligible recipients receive zero.

The implementation does not compute lambda as floating point. It repeatedly freezes one recipient whose cap is at or below its current proportional quota. After removing that cap and weight, it recomputes quotas for the remaining total. This is weighted water filling. When no cap binds, all remaining exact quotas share the denominator of the remaining weight sum.

## Why cap freezing terminates and preserves feasibility

A binding cap satisfies `cap <= floor(remaining * weight / weight_sum)`. Because the cap is an integer, this is equivalent to `cap <= exact quota`. Removing it cannot lower the residual proportional level, so an already-frozen cap remains binding. Each successful pass removes one positive-weight recipient, including when the cap is zero; there are at most N such passes. Positive residual capacity implies at least one remaining positive weight, so the denominator cannot be zero while the residual total is positive.

The initial capacity check includes only positive-weight recipients. Every frozen assignment consumes no more than the current remaining total. Once no cap binds, each unfrozen exact quota is strictly below its integer cap. Its ceiling is therefore at most that cap.

## Integer rounding

The sum of residual exact quotas is the remaining integer total. Subtracting their floors leaves an integer number of units equal to the sum of their fractional parts. It is nonnegative and strictly less than the number of active recipients. Giving at most one extra unit to distinct recipients with the largest remainders therefore assigns the whole total and never exceeds a cap. A positive number of unassigned units implies there are enough positive fractional remainders, so zero-weight or already-frozen recipients never need an extra unit.

Shares on success sum exactly to the requested total; every share is between zero and its cap. Each active result is a floor or ceiling of its continuous capped quota. This is a quota property, not a guarantee of house monotonicity, population monotonicity, or resistance to strategic identities.

## Arithmetic domain

Let M = 2^128 - 1. The public domain is `1 <= N <= 64` and all totals, weights and caps are in `[0, M]`.

| Operation | Bound and reason |
| --- | --- |
| Weight/capacity sums | At most `64*M < 2^134`, stored in `u256`. |
| Quota numerator | `remaining*weight <= M*M < 2^256`. Both operands originate as `u128`. |
| Quota division | Denominator includes the active weight, so the quotient is at most `remaining <= M`. The checked downcast to `u128` is justified by this bound. |
| Frozen-cap subtraction | A binding cap is at most its quota and hence at most `remaining`. |
| Floor sum | At most the residual total, because floors do not exceed exact quotas. Accumulating in `u128` is sufficient. |
| Bonus increment | The floor is below its integer cap; adding one stays at most `cap <= M`. |
| Tie scan | Offset is reduced modulo N; `start + rank <= 126`, so the `usize` addition is bounded. |

The binding-cap check deliberately divides the bounded numerator and compares the floor with the cap. Cross-multiplying `cap * weight_sum` would require up to 262 bits and would not fit `u256` for all supported inputs.

Fe checked operations and checked downcasts remain in place. Within the stated domain, the above bounds avoid arithmetic overflow; infeasible allocations return typed errors. There is no arbitrary-precision or wrapping-arithmetic fallback. A defect in these arguments or the compiler would still be a defect, which is why both boundary fixtures and executed cross-backend comparisons are included.

## Work bounds and representation

Cap freezing takes at most N scans of N entries. Rounding selects fewer than N recipients with a scan of N entries each. There is no per-unit loop over T, no sort allocation, and no recursion. Storage is a constant number of arrays of length N, so time is O(N²) and working space is O(N).

`saturated` records a procedural fact: the recipient was frozen at its cap before the residual-quota stage. It is intentionally different from final equality with the cap. `bonuses`, raw `remainders`, and the shared denominator explain the final rounding stage. Frozen/ineligible recipients have zero raw remainder; a skipped residual-quota stage has denominator zero. A nonzero denominator does not imply a bonus was needed.

## Independent checks

`tools/oracle.py` sorts exact rational `cap/weight` breakpoints, solves for the water level, then computes exact quotas using Python `Fraction`. That has a different control structure and unbounded arithmetic. The committed Fe fixtures exercise the compiled library; the larger native differential run executes the compiled native program for each case. `tools/test_cli.py` uses additional hand-computed expectations and checks all report fields and error handling.

An additional read-only AI-assisted review compared a transcription of the Fe allocation logic against a subset-enumerated rational solution over 82,488 small cases and 1,500 full-width random cases. That supplementary model check is not presented as an executed compiler test or a formal proof. The reproducible, packaged checks are the Fe fixtures and native executable tests.
