| **# Pools** | **Same-Pool Pairing**                        | **Near-pool Pairing**                       | **Half-Pool Pairing**                     | **Far-Pool Pairing**                     |
|-------------|----------------------------------------------|---------------------------------------------|-------------------------------------------|------------------------------------------|
| **2 Pools** | A1 vs A2, B1 vs B2                           | A1 vs B2, A2 vs B1                         | A1 vs A2, B1 vs B2 (same as "same-pool")  | A1 vs B2, A2 vs B1                       |
| **4 Pools** | A1 vs A2, B1 vs B2, C1 vs C2, D1 vs D2       | A1 vs B2, A2 vs B1, C1 vs D2, C2 vs D1     | A1 vs B2, A2 vs B1, C1 vs D2, C2 vs D1    | A1 vs D2, A2 vs D1, B1 vs C2, B2 vs C1   |
| **8 Pools** | A1 vs A2, B1 vs B2, C1 vs C2, D1 vs D2, E1 vs F2, G1 vs H2 | A1 vs B2, A2 vs B1, C1 vs D2, C2 vs D1, E1 vs F2, E2 vs F1, G1 vs H2, G2 vs H1 | A1 vs D2, A2 vs D1, E1 vs H2, H1 vs E2    | A1 vs H2, A2 vs H1, B1 vs G2, B2 vs G1, C1 vs F2, C2 vs F1, D1 vs E2, D2 vs E1 |

# Khel Club backend

This Flask application provides tournament, fixture, scoring, and bracket
advancement APIs for Khel Club. It uses SQLAlchemy with MySQL/MariaDB and
Socket.IO for live score updates.

## Current scoring mechanism (v0 score coupling)

The v0 scoring flow stores one `Score` row per team and match. The
`POST /update-score` endpoint receives a hyphenated string such as `11-7`,
parses both values as integers, creates or updates the two score rows, and
optionally finalizes the match. On finalization, the route compares the two
numbers to set `Match.winner_team_id`. A finalized match is then advanced to
its successor bracket match, if one exists, and the same response is emitted
on the `/scores` Socket.IO namespace.

This design assumes every completed match has numeric scores. It also mixes
score persistence, outcome/winner rules, and bracket/status transitions in one
route, which made non-scoring outcomes difficult to represent.

## Outcome support and Strategy Pattern

`outcome_service.py` centralizes outcome rules behind
`MatchOutcomeStrategy.resolve(match, data, team1_score, team2_score)`.

- `RegularOutcomeStrategy` compares numeric scores and allows a draw when
  scores are equal.
- `WalkoverOutcomeStrategy` accepts an explicit `winner_team_id`, or derives
  the winner as the team opposite `conceded_by_team_id`. It marks the match
  `WALKOVER` and completed without relying on numeric scores.
- `ForfeitOutcomeStrategy` and `ByeOutcomeStrategy` are ready concrete
  strategies with their own outcome names and the same winner-selection
  contract.
- `OutcomeRegistry` maps an uppercase outcome name to its strategy. Adding a
  new outcome requires registering a strategy rather than adding another
  branch to the score route.

Match status is separate from outcome. A walkover is always completed, while
regular matches resolve their winner only when the request is final. The score
endpoint includes `outcome` and `winner_team_id` in its JSON response and live
`score_update` event.

## Schema and migration

Run `migrations/add_match_outcome.sql` against the existing database:

```sql
ALTER TABLE `match` ADD COLUMN outcome VARCHAR(30) DEFAULT 'REGULAR' NOT NULL;
ALTER TABLE `match` ADD COLUMN conceded_by_team_id VARCHAR(50) NULL;
ALTER TABLE `match` ADD COLUMN outcome_reason VARCHAR(255) NULL;
```

The SQLAlchemy `Match` model mirrors these columns. Fixture responses expose
`outcome` and `winner_team_id`; `/score/match` additionally returns
`conceded_by_team_id` and `outcome_reason`.

## Walkover API

The referee UI submits:

```json
{
  "tournament_id": 85,
  "match_id": 123,
  "outcome": "WALKOVER",
  "winner_team_id": "team-a",
  "score": "0-0",
  "final": true
}
```

Walkovers are shown as `WALKOVER` in fixture and match-table responses, and
the winning team is highlighted by the frontend. A successor match receives
the winner through the existing bracket advancement helper.

## Assumptions

- Walkovers are non-scoring results represented by `0-0` score rows so
  existing v0 consumers continue to work.
- The selected winner must be one of the two teams assigned to the match.
- A walkover is final and completed immediately.
- Bracket advancement uses the existing successor/predecessor relationships.
- Existing regular scoring and status endpoints remain backward compatible.
- Migrations are run explicitly; `db.create_all()` does not alter an existing
  `match` table.

## Potential improvements

With more time, the backend should gain unit tests for every strategy,
invalid winner/concession combinations, and successor advancement. Tie-breaker
rules and sport-specific score validation should be extracted from the regular
strategy. Outcome changes would benefit from audit logging (referee,
timestamp, and reason), and migrations could be managed through a formal
versioned migration tool rather than standalone SQL files.
