from __future__ import annotations

import json
from typing import Any
import pandas as pd

SYSTEM = """You are Shiva, an elite fantasy-football draft analyst inside a live draft application.
Your job is to make useful, decisive recommendations for ESPN-style full PPR redraft leagues.
Never invent stats. Distinguish verified app data from general football judgment. If a statistic is not in the supplied context, say that clearly.
For live pick advice, explicitly account for: current roster construction, positions already drafted, top available players, ADP, round, next user pick, positional scarcity, and roster balance.
Do not mechanically say 'best player available.' Explain opportunity cost. Prefer concise answers with a clear recommendation first.
The supplied draft state is authoritative for who is available and who has already been drafted.
"""


def rankings_context(rankings: pd.DataFrame, limit: int = 90) -> list[dict[str, Any]]:
    cols = [c for c in ["player_name", "team", "position", "position_rank", "adp", "overall_rank", "bye"] if c in rankings.columns]
    frame = rankings.sort_values("adp", na_position="last").head(limit)[cols].copy()
    return frame.where(pd.notna(frame), None).to_dict("records")


def build_context(*, rankings: pd.DataFrame, watchlist: list[str], draft: dict | None, history_summary: str = "") -> str:
    payload: dict[str, Any] = {
        "current_rankings": rankings_context(rankings),
        "watchlist": watchlist,
        "historical_database_summary": history_summary,
    }
    if draft:
        payload["live_draft"] = draft
    return json.dumps(payload, ensure_ascii=False, default=str)


def ask_shiva(api_key: str, model: str, question: str, context: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        instructions=SYSTEM,
        input=f"APP CONTEXT:\n{context}\n\nUSER QUESTION:\n{question}",
        store=False,
    )
    return response.output_text.strip()
