from abc import ABC, abstractmethod


class MatchOutcomeStrategy(ABC):
    """Resolve the winner and state for one match outcome."""

    @abstractmethod
    def resolve(self, match, data, team1_score, team2_score):
        """Apply the outcome to ``match`` and return its winning team ID."""


class RegularOutcomeStrategy(MatchOutcomeStrategy):
    def resolve(self, match, data, team1_score, team2_score):
        match.outcome = "REGULAR"
        if team1_score > team2_score:
            match.winner_team_id = match.team1_id
        elif team2_score > team1_score:
            match.winner_team_id = match.team2_id
        else:
            match.winner_team_id = None
        return match.winner_team_id


class WalkoverOutcomeStrategy(MatchOutcomeStrategy):
    outcome_name = "WALKOVER"

    def resolve(self, match, data, team1_score, team2_score):
        winner_team_id = data.get("winner_team_id")
        conceded_by_team_id = data.get("conceded_by_team_id")

        valid_team_ids = {match.team1_id, match.team2_id}
        if winner_team_id and winner_team_id not in valid_team_ids:
            raise ValueError("winner_team_id must belong to one of the match teams")
        if conceded_by_team_id and conceded_by_team_id not in valid_team_ids:
            raise ValueError("conceded_by_team_id must belong to one of the match teams")

        if not winner_team_id and conceded_by_team_id:
            winner_team_id = (
                match.team2_id
                if conceded_by_team_id == match.team1_id
                else match.team1_id
            )

        if not winner_team_id:
            raise ValueError("winner_team_id or conceded_by_team_id is required")
        if conceded_by_team_id == winner_team_id:
            raise ValueError("winner_team_id and conceded_by_team_id must differ")

        match.winner_team_id = winner_team_id
        match.outcome = self.outcome_name
        match.conceded_by_team_id = conceded_by_team_id
        match.outcome_reason = data.get("outcome_reason")
        match.status = "completed"
        return winner_team_id


class ForfeitOutcomeStrategy(WalkoverOutcomeStrategy):
    outcome_name = "FORFEIT"


class ByeOutcomeStrategy(WalkoverOutcomeStrategy):
    outcome_name = "BYE"


class OutcomeRegistry:
    _strategies = {
        "REGULAR": RegularOutcomeStrategy(),
        "WALKOVER": WalkoverOutcomeStrategy(),
        "FORFEIT": ForfeitOutcomeStrategy(),
        "BYE": ByeOutcomeStrategy(),
    }

    @classmethod
    def get(cls, outcome):
        try:
            return cls._strategies[outcome.upper()]
        except (AttributeError, KeyError) as exc:
            raise ValueError(f"Unsupported match outcome: {outcome}") from exc
