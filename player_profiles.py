from __future__ import annotations

import re
import unicodedata
import pandas as pd
import streamlit as st


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", value)
    return re.sub(r"[^a-z0-9]+", "", value)


@st.cache_data(show_spinner=False, ttl=3600)
def _weekly(season: int) -> pd.DataFrame:
    url = f"https://github.com/nflverse/nflverse-data/releases/download/player_stats/stats_player_week_{int(season)}.csv"
    try:
        df = pd.read_csv(url)
    except Exception:
        return pd.DataFrame()
    name_col = next((c for c in ["player_display_name", "player_name", "display_name", "name"] if c in df.columns), None)
    if not name_col:
        return pd.DataFrame()
    df["_name_key"] = df[name_col].map(_norm)
    return df


def open_profile(name: str, return_page: str) -> None:
    st.session_state["selected_player"] = str(name)
    st.session_state["profile_return_page"] = return_page
    st.session_state["page"] = "Player Profile"
    st.rerun()


def render_top_board(rankings: pd.DataFrame, return_page: str = "Shiva Intelligence") -> None:
    st.markdown("### 2026 Top of the Board")
    st.caption("Tap a player for the full profile, prior-season summary and week-by-week scoring.")
    for i, (_, row) in enumerate(rankings.head(8).iterrows(), start=1):
        st.caption(f"#{i} overall · {row.position} · {row.team} · ADP {float(row.adp):.1f}")
        if st.button(str(row.player_name), key=f"top_board_profile_{i}", use_container_width=True):
            open_profile(str(row.player_name), return_page)


def render_player_profile(name: str, rankings: pd.DataFrame, history: pd.DataFrame) -> None:
    if st.button("← Back", key="player_profile_back"):
        st.session_state["page"] = st.session_state.get("profile_return_page", "Shiva Intelligence")
        st.rerun()

    ranked = rankings[rankings.player_name.astype(str).eq(str(name))]
    row = ranked.iloc[0] if not ranked.empty else None
    team = str(row.team) if row is not None and pd.notna(row.team) else ""
    pos = str(row.position) if row is not None and pd.notna(row.position) else ""
    adp = float(row.adp) if row is not None and pd.notna(row.adp) else None
    pos_rank = int(row.position_rank) if row is not None and pd.notna(row.position_rank) else None

    st.markdown(f"## {name}")
    meta = [x for x in [team, pos, f"{pos}{pos_rank}" if pos_rank else "", f"2026 ADP {adp:.1f}" if adp is not None else ""] if x]
    st.caption(" · ".join(meta))

    hist = history.copy()
    if not hist.empty and "player_name" in hist.columns:
        hist = hist[hist.player_name.map(_norm).eq(_norm(name))]

    seasons = []
    if not hist.empty and "season" in hist.columns:
        seasons = sorted({int(x) for x in hist.season.dropna().tolist() if int(x) <= 2025}, reverse=True)
    if not seasons:
        seasons = list(range(2025, 2011, -1))

    season = st.selectbox("Season", seasons, key=f"profile_year_{_norm(name)}")
    hs = hist[hist.season.eq(int(season))] if not hist.empty and "season" in hist.columns else pd.DataFrame()
    summary = hs.iloc[0] if not hs.empty else None

    ppg = float(summary.ppg) if summary is not None and "ppg" in hs.columns and pd.notna(summary.ppg) else None
    total = float(summary.fantasy_points_ppr) if summary is not None and "fantasy_points_ppr" in hs.columns and pd.notna(summary.fantasy_points_ppr) else None
    finish = int(summary.position_finish_total) if summary is not None and "position_finish_total" in hs.columns and pd.notna(summary.position_finish_total) else None

    weekly = _weekly(int(season))
    if not weekly.empty:
        weekly = weekly[weekly["_name_key"].eq(_norm(name))].copy()
        if "season_type" in weekly.columns:
            reg = weekly[weekly.season_type.astype(str).str.upper().eq("REG")]
            if not reg.empty:
                weekly = reg

    fp_col = "fantasy_points_ppr" if "fantasy_points_ppr" in weekly.columns else ("fantasy_points" if "fantasy_points" in weekly.columns else None)
    if ppg is None and fp_col and not weekly.empty:
        ppg = float(pd.to_numeric(weekly[fp_col], errors="coerce").mean())
    if total is None and fp_col and not weekly.empty:
        total = float(pd.to_numeric(weekly[fp_col], errors="coerce").sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("PPR PPG", "—" if ppg is None else f"{ppg:.1f}")
    c2.metric("PPR Points", "—" if total is None else f"{total:.1f}")
    c3.metric("Pos Finish", "—" if finish is None else f"#{finish}")

    st.markdown("### Week-by-week scoring")
    if weekly.empty or not fp_col:
        st.info(f"Weekly scoring for {season} is not available from the current data feed.")
        return

    if "week" in weekly.columns:
        weekly["week"] = pd.to_numeric(weekly["week"], errors="coerce")
        weekly = weekly.sort_values("week")

    opp_col = next((c for c in ["opponent_team", "opponent", "opp"] if c in weekly.columns), None)
    team_col = next((c for c in ["recent_team", "team"] if c in weekly.columns), None)

    for _, w in weekly.iterrows():
        wk = int(w.week) if "week" in weekly.columns and pd.notna(w.week) else "—"
        opp = str(w[opp_col]) if opp_col and pd.notna(w[opp_col]) else "—"
        own = str(w[team_col]) if team_col and pd.notna(w[team_col]) else team
        pts = float(w[fp_col]) if pd.notna(w[fp_col]) else 0.0
        st.markdown(f"**Week {wk}** · {own} vs {opp} — **{pts:.1f} PPR**")
