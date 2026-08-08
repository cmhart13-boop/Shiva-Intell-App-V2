from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import math
import pandas as pd

STARTER_TARGETS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}
MAX_REASONABLE = {"QB": 2, "RB": 7, "WR": 7, "TE": 3}


@dataclass(frozen=True)
class DraftConfig:
    teams: int = 10
    rounds: int = 16
    user_slot: int = 4
    scoring: str = "PPR"


def pick_team(overall_pick: int, teams: int) -> int:
    round_number = math.ceil(overall_pick / teams)
    within = ((overall_pick - 1) % teams) + 1
    return within if round_number % 2 else teams - within + 1


def pick_round(overall_pick: int, teams: int) -> int:
    return math.ceil(overall_pick / teams)


def slot_picks(slot: int, teams: int, rounds: int) -> list[int]:
    picks: list[int] = []
    for rnd in range(1, rounds + 1):
        picks.append((rnd - 1) * teams + slot if rnd % 2 else rnd * teams - slot + 1)
    return picks


def roster_counts(picks: Iterable[dict], team: int) -> dict[str, int]:
    counts = {"QB": 0, "RB": 0, "WR": 0, "TE": 0}
    for p in picks:
        if int(p.get("team", -1)) == team:
            pos = str(p.get("position", "")).upper()
            if pos in counts:
                counts[pos] += 1
    return counts


def available_players(rankings: pd.DataFrame, picks: list[dict]) -> pd.DataFrame:
    drafted = {str(p["player_name"]) for p in picks}
    out = rankings[~rankings["player_name"].astype(str).isin(drafted)].copy()
    return out.sort_values(["adp", "overall_rank"], na_position="last")


def _need_bonus(position: str, counts: dict[str, int], rnd: int) -> float:
    pos = position.upper()
    bonus = 0.0
    if pos in STARTER_TARGETS and counts.get(pos, 0) < STARTER_TARGETS[pos]:
        bonus += 9.0
    if pos in {"RB", "WR"} and rnd <= 5:
        bonus += 4.5
    if pos == "QB" and rnd <= 2:
        bonus -= 9.0
    if pos == "TE" and rnd <= 2:
        bonus -= 4.0
    if pos == "QB" and counts.get("QB", 0) >= 1 and rnd <= 8:
        bonus -= 7.0
    if counts.get(pos, 0) >= MAX_REASONABLE.get(pos, 99):
        bonus -= 30.0
    return bonus


def score_board(rankings: pd.DataFrame, picks: list[dict], team: int, overall_pick: int, teams: int | None = None) -> pd.DataFrame:
    avail = available_players(rankings, picks).copy()
    if avail.empty:
        return avail
    teams = teams or max(1, max([int(p.get("team", 0)) for p in picks] + [team]))
    rnd = pick_round(overall_pick, teams)
    counts = roster_counts(picks, team)
    avail["adp"] = pd.to_numeric(avail["adp"], errors="coerce")
    base = 120 - avail["adp"].fillna(250).clip(1, 250) * 0.45
    proximity = (12 - (avail["adp"].fillna(overall_pick) - overall_pick).abs()).clip(-12, 12) * 0.6
    avail["draft_score"] = [
        float(base.loc[idx]) + float(proximity.loc[idx]) + _need_bonus(str(row["position"]), counts, rnd)
        for idx, row in avail.iterrows()
    ]
    return avail.sort_values(["draft_score", "adp"], ascending=[False, True])


def cpu_choice(rankings: pd.DataFrame, picks: list[dict], team: int, overall_pick: int, teams: int) -> dict:
    board = available_players(rankings, picks).head(45).copy()
    counts = roster_counts(picks, team)
    rnd = pick_round(overall_pick, teams)
    if board.empty:
        raise ValueError("No players remain")
    board["adp"] = pd.to_numeric(board["adp"], errors="coerce")
    board["cpu_score"] = 130 - board["adp"].fillna(250) * 0.5 + board["position"].map(lambda p: _need_bonus(str(p), counts, rnd))
    row = board.sort_values(["cpu_score", "adp"], ascending=[False, True]).iloc[0]
    return row.to_dict()


def make_pick(player: dict, overall_pick: int, teams: int) -> dict:
    return {
        "overall": int(overall_pick),
        "round": pick_round(overall_pick, teams),
        "team": pick_team(overall_pick, teams),
        "player_name": str(player["player_name"]),
        "position": str(player["position"]),
        "nfl_team": str(player.get("team", "")),
        "adp": float(player.get("adp")) if pd.notna(player.get("adp")) else None,
    }


def advance_cpus(rankings: pd.DataFrame, picks: list[dict], next_pick: int, config: DraftConfig) -> tuple[list[dict], int]:
    total = config.teams * config.rounds
    while next_pick <= total and pick_team(next_pick, config.teams) != config.user_slot:
        team = pick_team(next_pick, config.teams)
        player = cpu_choice(rankings, picks, team, next_pick, config.teams)
        picks.append(make_pick(player, next_pick, config.teams))
        next_pick += 1
    return picks, next_pick


def user_roster(picks: list[dict], slot: int) -> list[dict]:
    return [p for p in picks if int(p["team"]) == int(slot)]


def board_matrix(picks: list[dict], teams: int, rounds: int) -> list[list[dict | None]]:
    lookup = {(int(p["round"]), int(p["team"])): p for p in picks}
    return [[lookup.get((rnd, team)) for team in range(1, teams + 1)] for rnd in range(1, rounds + 1)]
