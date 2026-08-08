from __future__ import annotations

import html
import re
import unicodedata
import pandas as pd
import streamlit as st


def _norm(v: str) -> str:
    v = unicodedata.normalize("NFKD", str(v or "")).encode("ascii", "ignore").decode().lower()
    v = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", v)
    return re.sub(r"[^a-z0-9]+", "", v)


def _n(v, default=0.0):
    try:
        return default if pd.isna(v) else float(v)
    except Exception:
        return default


def _i(v, default=0):
    try:
        return default if pd.isna(v) else int(float(v))
    except Exception:
        return default


@st.cache_data(show_spinner=False, ttl=3600)
def _weekly(season: int) -> pd.DataFrame:
    url = f"https://github.com/nflverse/nflverse-data/releases/download/player_stats/stats_player_week_{season}.csv"
    try:
        df = pd.read_csv(url)
    except Exception:
        return pd.DataFrame()
    name_col = next((c for c in ["player_display_name", "player_name", "display_name", "name"] if c in df.columns), None)
    if not name_col:
        return pd.DataFrame()
    df["_key"] = df[name_col].map(_norm)
    return df


@st.cache_data(show_spinner=False, ttl=21600)
def _roster(season: int) -> pd.DataFrame:
    url = f"https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_{season}.csv"
    try:
        df = pd.read_csv(url)
    except Exception:
        return pd.DataFrame()
    name_col = next((c for c in ["full_name", "player_name", "display_name", "name"] if c in df.columns), None)
    if not name_col:
        return pd.DataFrame()
    df["_key"] = df[name_col].map(_norm)
    return df


def _player_weeks(name: str, season: int) -> pd.DataFrame:
    df = _weekly(season)
    if df.empty:
        return df
    df = df[df["_key"].eq(_norm(name))].copy()
    if "season_type" in df.columns:
        reg = df[df["season_type"].astype(str).str.upper().eq("REG")]
        if not reg.empty:
            df = reg
    if "week" in df.columns:
        df["week"] = pd.to_numeric(df["week"], errors="coerce")
        df = df.sort_values("week")
    return df


def _roster_row(name: str):
    for season in (2026, 2025, 2024):
        df = _roster(season)
        if not df.empty:
            hit = df[df["_key"].eq(_norm(name))]
            if not hit.empty:
                return hit.iloc[0]
    return None


def _first(row, cols, default=""):
    if row is None:
        return default
    for c in cols:
        if c in row.index and pd.notna(row[c]):
            return row[c]
    return default


def _fp_col(df):
    if "fantasy_points_ppr" in df.columns:
        return "fantasy_points_ppr"
    if "fantasy_points" in df.columns:
        return "fantasy_points"
    return None


def _sum(df, col):
    return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum()) if col in df.columns and not df.empty else 0.0


def _avg(df, col):
    if col not in df.columns or df.empty:
        return 0.0
    s = pd.to_numeric(df[col], errors="coerce")
    return float(s.mean()) if s.notna().any() else 0.0


def _css():
    st.markdown("""
    <style>
    .block-container{padding-top:.55rem!important;max-width:920px!important}
    .pp-hero{position:relative;overflow:hidden;min-height:285px;border-radius:24px 24px 0 0;background:linear-gradient(180deg,#183047,#222 58%);padding:32px;color:#fff}
    .pp-name{position:relative;z-index:2;font-size:2.05rem;font-weight:900;letter-spacing:-.03em}.pp-meta{position:relative;z-index:2;font-size:1.16rem;display:flex;align-items:center;gap:9px}
    .pp-logo{width:34px;height:34px;object-fit:contain}.pp-shot{position:absolute;right:1%;bottom:0;height:255px;max-width:49%;object-fit:contain;object-position:bottom right}
    .pp-metrics{position:relative;z-index:3;margin-top:150px;border:2px solid #484a4c;border-radius:22px;background:#272829ed;display:grid;grid-template-columns:repeat(4,1fr);padding:18px 5px}
    .pp-m{text-align:center}.pp-v{font-size:1.9rem;font-weight:850}.pp-l{font-size:.83rem;color:#aaa;margin-top:6px;white-space:nowrap}
    .pp-card{background:#242526;border-radius:22px;padding:25px 28px;margin-top:18px}.pp-title{font-size:1.28rem;font-weight:850}.pp-rule{border-top:1px dotted #555;margin:16px 0}
    .pp-wrap{overflow-x:auto;margin:0 -28px -25px}.pp-table{width:100%;border-collapse:collapse;min-width:625px}.pp-table th{background:#1e1f20;color:#fff;padding:13px 8px}.pp-table td{padding:18px 8px;text-align:center;color:#b7b7b7;border-bottom:1px solid #2b2d2f}.pp-table tr:nth-child(odd) td{background:#2a2b2c}.pp-table tr:nth-child(even) td{background:#222324}.pp-table .strong{font-weight:800;color:#d0d0d0}
    div[role="radiogroup"]{display:flex!important;justify-content:space-between!important;border-top:1px solid #3b3d3f;border-bottom:1px solid #3b3d3f;padding:10px 4px 4px}div[role="radiogroup"] label[data-baseweb="radio"]>div:first-child{display:none!important}div[role="radiogroup"] label{font-weight:700!important;color:#aaa!important}
    @media(max-width:700px){.block-container{padding-left:0!important;padding-right:0!important}.pp-hero{border-radius:0;padding:24px 18px;min-height:250px}.pp-name{font-size:1.72rem}.pp-shot{height:215px;max-width:54%}.pp-metrics{margin-top:126px;padding:14px 2px}.pp-v{font-size:1.48rem}.pp-l{font-size:.66rem}.pp-card{border-radius:18px;padding:21px 18px}.pp-wrap{margin:0 -18px -21px}div[role="radiogroup"]{overflow-x:auto!important;justify-content:flex-start!important;gap:14px!important;padding-left:10px}div[role="radiogroup"] label{white-space:nowrap!important;font-size:.84rem!important}}
    </style>
    """, unsafe_allow_html=True)


def open_profile(name: str, return_page: str) -> None:
    st.session_state["selected_player"] = str(name)
    st.session_state["profile_return_page"] = return_page
    st.session_state["page"] = "Player Profile"
    st.rerun()


def render_top_board(rankings: pd.DataFrame, return_page: str = "Shiva Intelligence") -> None:
    st.markdown("### 2026 Top of the Board")
    for i, (_, row) in enumerate(rankings.head(8).iterrows(), start=1):
        st.caption(f"#{i} overall · {row.position} · {row.team} · ADP {float(row.adp):.1f}")
        if st.button(str(row.player_name), key=f"top_board_profile_{i}", use_container_width=True):
            open_profile(str(row.player_name), return_page)


def _hero(name, team, pos, pos_rank, adp, rr, weeks26):
    headshot = str(_first(rr, ["headshot_url", "headshot", "player_headshot"], ""))
    espn_id = _i(_first(rr, ["espn_id", "espn_player_id"], 0), 0)
    if not headshot and espn_id:
        headshot = f"https://a.espncdn.com/i/headshots/nfl/players/full/{espn_id}.png"
    jersey = _i(_first(rr, ["jersey_number", "jersey", "number"], 0), 0)
    logo = f"https://a.espncdn.com/i/teamlogos/nfl/500/{team.lower()}.png" if team else ""
    fp = _fp_col(weeks26)
    ppg = _avg(weeks26, fp) if fp else 0.0
    total = _sum(weeks26, fp) if fp else 0.0
    logo_html = f'<img class="pp-logo" src="{html.escape(logo)}">' if logo else ""
    shot_html = f'<img class="pp-shot" src="{html.escape(headshot)}">' if headshot else ""
    rank = str(pos_rank) if pos_rank else "—"
    adp_text = f"{adp:.1f}" if adp is not None else "—"
    number = f" · #{jersey}" if jersey else ""
    st.markdown(f"""
    <div class="pp-hero"><div class="pp-name">{html.escape(name.upper())}</div><div class="pp-meta">{logo_html}<span>{html.escape(team)} · {html.escape(pos)}{number}</span></div>{shot_html}
    <div class="pp-metrics"><div class="pp-m"><div class="pp-v">{rank}</div><div class="pp-l">POS RANK</div></div><div class="pp-m"><div class="pp-v">{ppg:.1f}</div><div class="pp-l">AVG FPTS</div></div><div class="pp-m"><div class="pp-v">{total:.1f}</div><div class="pp-l">2026 FPTS</div></div><div class="pp-m"><div class="pp-v">{adp_text}</div><div class="pp-l">2026 ADP</div></div></div></div>
    """, unsafe_allow_html=True)


def _game_log(name, pos, season, df):
    fp = _fp_col(df)
    st.markdown(f'<div class="pp-card"><div class="pp-title">{season} REGULAR SEASON</div><div class="pp-rule"></div>', unsafe_allow_html=True)
    if df.empty or not fp:
        st.info(f"No regular-season weekly data is available yet for {name} in {season}.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    if pos.upper() == "QB":
        headers = ["WK","OPP","FPTS","YDS","TD","I/F"]
        rows = [[_i(w.get("week")),w.get("opponent_team","—"),_n(w.get(fp)),_i(w.get("passing_yards")),_i(w.get("passing_tds")),f'{_i(w.get("interceptions"))}/{_i(w.get("sack_fumbles_lost"))}'] for _,w in df.iterrows()]
    elif pos.upper() in {"RB","FB"}:
        headers = ["WK","OPP","FPTS","RUSH YDS","REC YDS","TD"]
        rows = [[_i(w.get("week")),w.get("opponent_team","—"),_n(w.get(fp)),_i(w.get("rushing_yards")),_i(w.get("receiving_yards")),_i(w.get("rushing_tds"))+_i(w.get("receiving_tds"))] for _,w in df.iterrows()]
    else:
        headers = ["WK","OPP","FPTS","REC","YDS","TD"]
        rows = [[_i(w.get("week")),w.get("opponent_team","—"),_n(w.get(fp)),_i(w.get("receptions")),_i(w.get("receiving_yards")),_i(w.get("receiving_tds"))] for _,w in df.iterrows()]
    th = "".join(f"<th>{html.escape(str(x))}</th>" for x in headers)
    body = ""
    for r in rows:
        cells=[]
        for j,x in enumerate(r):
            text=f"{x:.1f}" if j==2 else str(x)
            cells.append(f'<td class="strong">{html.escape(text)}</td>' if j==2 else f'<td>{html.escape(text)}</td>')
        body += "<tr>"+"".join(cells)+"</tr>"
    st.markdown(f'<div class="pp-wrap"><table class="pp-table"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div></div>', unsafe_allow_html=True)


def _stats(pos, season, df):
    fp = _fp_col(df)
    st.markdown(f'<div class="pp-card"><div class="pp-title">{season} STATS</div><div class="pp-rule"></div>', unsafe_allow_html=True)
    c1,c2,c3=st.columns(3); c1.metric("Games",len(df)); c2.metric("PPR Points",f"{_sum(df,fp):.1f}" if fp else "0.0"); c3.metric("PPR / Game",f"{_avg(df,fp):.1f}" if fp else "0.0")
    if pos.upper()=="QB": cols=[("Pass Yds","passing_yards"),("Pass TD","passing_tds"),("INT","interceptions"),("Rush Yds","rushing_yards")]
    elif pos.upper() in {"RB","FB"}: cols=[("Carries","carries"),("Rush Yds","rushing_yards"),("Receptions","receptions"),("Rec Yds","receiving_yards")]
    else: cols=[("Targets","targets"),("Receptions","receptions"),("Rec Yds","receiving_yards"),("Rec TD","receiving_tds")]
    cc=st.columns(4)
    for col,(label,key) in zip(cc,cols): col.metric(label,f"{_sum(df,key):.0f}")
    st.markdown('</div>',unsafe_allow_html=True)


def render_player_profile(name: str, rankings: pd.DataFrame, history: pd.DataFrame) -> None:
    _css()
    if st.button("← Back", key="player_profile_back"):
        st.session_state["page"] = st.session_state.get("profile_return_page", "Shiva Intelligence")
        st.rerun()

    ranked = rankings[rankings.player_name.astype(str).map(_norm).eq(_norm(name))] if not rankings.empty and "player_name" in rankings.columns else pd.DataFrame()
    row = ranked.iloc[0] if not ranked.empty else None
    rr = _roster_row(name)
    team = str(_first(row,["team","recent_team"],_first(rr,["team","recent_team"],"")))
    pos = str(_first(row,["position","pos"],_first(rr,["position","pos"],"")))
    adp_raw = _first(row,["adp","espn_adp"],None); adp = None if adp_raw is None or pd.isna(adp_raw) else float(adp_raw)
    rank_raw = _first(row,["position_rank","pos_rank"],None); pos_rank = None if rank_raw is None or pd.isna(rank_raw) else int(float(rank_raw))

    hist = history.copy() if history is not None else pd.DataFrame()
    if not hist.empty and "player_name" in hist.columns: hist=hist[hist.player_name.map(_norm).eq(_norm(name))]
    seasons = sorted({int(x) for x in hist.get("season",pd.Series(dtype=float)).dropna() if int(x)<=2025}, reverse=True) or list(range(2025,2012,-1))

    _hero(name,team,pos,pos_rank,adp,rr,_player_weeks(name,2026))
    tab = st.radio("section",["Overview","News","Stats","Odds","Game Log","Projections"],index=4,horizontal=True,label_visibility="collapsed",key=f"profile_tab_{_norm(name)}")
    _,right=st.columns([3,1])
    with right: season=st.selectbox("Season",seasons,label_visibility="collapsed",key=f"profile_year_{_norm(name)}")
    weeks=_player_weeks(name,int(season))

    if tab=="Game Log": _game_log(name,pos,int(season),weeks)
    elif tab=="Stats": _stats(pos,int(season),weeks)
    elif tab=="Overview":
        _stats(pos,int(season),weeks)
        st.markdown(f'<div class="pp-card"><div class="pp-title">PLAYER OVERVIEW</div><div class="pp-rule"></div>{html.escape(name)} · {html.escape(team)} · {html.escape(pos)}<br>2026 ADP: {"—" if adp is None else f"{adp:.1f}"}<br>2026 position rank: {"—" if pos_rank is None else f"{html.escape(pos)}{pos_rank}"}</div>',unsafe_allow_html=True)
    elif tab=="Projections":
        proj=next((c for c in ["projected_points","projection","projected_fantasy_points","fpts"] if row is not None and c in row.index and pd.notna(row[c])),None)
        st.markdown('<div class="pp-card"><div class="pp-title">2026 PROJECTIONS</div><div class="pp-rule"></div>',unsafe_allow_html=True)
        if proj: st.metric("Projected PPR Points",f"{float(row[proj]):.1f}")
        else: st.info("No verified projection is present in the current rankings feed, so this profile will not fabricate one.")
        st.markdown('</div>',unsafe_allow_html=True)
    elif tab=="News": st.info("A verified live player-news feed is not connected yet. No headlines will be invented.")
    else: st.info("A verified live odds feed is not connected yet. No betting lines will be estimated.")
