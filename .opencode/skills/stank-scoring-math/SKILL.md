---
name: stank-scoring-math
description: Enforces stank-bot scoring invariants when editing scoring_service.py, chain_service.py, or scoring-related settings. Trigger when modifying SP/PP formulas, position bonuses, finish bonus, Team Player, or ScoringConfig.
---

# stank-bot scoring math invariants

## Core rules

1. **SP is always non-negative.** No code path may produce a negative SP award. SP represents earned rewards — use PP for penalties.

2. **PP is always non-positive (stored as positive, displayed as negative).** PP represents punishment. The `pp_awarded` field in `ChainResult` is a positive integer; the display layer negates it.

3. **Break PP formula:** `pp_break_base + (broken_chain_length × pp_break_per_stank)`. Both components come from `ScoringConfig`. The formula is applied in `scoring_service.compute_break_penalty()`.

4. **Position bonus:** The Nth valid stank in a chain earns `sp_flat + (N - 1)`. Position 1 (chain starter) gets `sp_flat + 0` plus the separate `sp_starter_bonus`.

5. **Team Player bonus:** Awarded when a user contributes to a chain that already has contributions from other users. Amount: `sp_team_player_bonus`. Checked via `chain_unique > 1` at the time of the stank.

6. **Finish bonus:** On chain break, retroactively awarded to the last valid stanker who is NOT the chainbreaker. Walks back `chain_messages` to find the recipient. If the entire chain was built by the breaker alone, no finish bonus is awarded.

7. **`ScoringConfig` is frozen.** It is a `@dataclass(frozen=True, slots=True)`. Never add mutable fields. All values come from guild settings at the time the chain event is processed — they are not stored on the chain itself.

8. **Reaction SP:** `sp_reaction` per first-time (message, user, sticker) tuple. Subsequent reactions by the same user on the same message with the same sticker are no-ops (enforced by `reaction_awards` unique constraint).

## When modifying scoring

- Update the corresponding unit tests in `tests/unit/test_scoring_service.py`.
- If changing defaults, update `AGENTS.md` section "SP / PP math" and the README scoring table.
- If adding a new bonus type, add a corresponding `Keys.*` setting so it's admin-configurable from day one.
- Never hardcode scoring values — they must flow through `ScoringConfig`.
