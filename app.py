from __future__ import annotations

import base64
import os
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import streamlit as st

from shiva_ai import ask_shiva, build_context
from shiva_draft import (
    DraftConfig,
    advance_cpus,
    available_players,
    board_matrix,
    make_pick,
    pick_team,
    roster_counts,
    score_board,
    user_roster,
)

ROOT = Path(__file__).resolve().parent
RANKINGS_PATH = ROOT / "current_rankings.csv"
DB_PATH = ROOT / "shiva_draft_roi.sqlite"
SPLASH_PATH = ROOT / "assets" / "shiva_splash.b64"
MODEL = "gpt-5-mini"

st.set_page_config(
    page_title="Shiva Intelligence",
    page_icon="🏆",
    layout="centered",
    initial_sidebar_state="collapsed",
)

CSS = r"""
<style>
:root{
 --bg:#02070c; --panel:#07131e; --panel2:#0a1b29; --line:#18344a;
 --text:#f7fbff; --muted:#9eb0bf; --lime:#d9ff00; --blue:#0397e6;
 --cyan:#33c9ff; --purple:#9348dd; --gold:#ffad16; --pink:#ef4f96;
 --green:#48b847; --qb:#b9252c; --rb:#df6905; --wr:#0c80c5;
 --te:#359c38; --flex:#7740aa; --k:#48545e; --def:#78501d;
}
html,body,[class*="css"]{font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;-webkit-font-smoothing:antialiased}
html,body{background:var(--bg)!important;overflow-x:hidden!important}
.stApp{background:radial-gradient(circle at 50% -12%,#0f2a43 0,#06131f 34%,#02070c 72%)!important;color:var(--text)!important}
.block-container{width:100%!important;max-width:520px!important;padding:8px 14px 88px!important;margin:0 auto!important}
#MainMenu,footer,header,[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important}
h1,h2,h3,p,label,.stMarkdown{color:var(--text)}
a{text-decoration:none!important}
div[data-testid="stHorizontalBlock"]{gap:8px!important;align-items:stretch!important}
div[data-testid="stHorizontalBlock"]>div[data-testid="stColumn"]{min-width:0!important}
@keyframes shivaSplashOut{0%,88%{opacity:1;visibility:visible}100%{opacity:0;visibility:hidden;pointer-events:none}}
.shiva-splash{position:fixed;inset:0;z-index:2147483647;background:#03156d;display:flex;justify-content:center;align-items:center;animation:shivaSplashOut 2.5s linear forwards}
.shiva-splash img{width:100vw;height:100dvh;object-fit:cover;object-position:center top;display:block}
@media(min-width:520px){.shiva-splash img{width:520px}}
.topbar{position:sticky;top:0;z-index:40;margin:0 -14px 10px;padding:10px 16px 9px;background:rgba(2,7,12,.95);border-bottom:1px solid #10283a;backdrop-filter:blur(14px)}
.top-brand{color:var(--lime);font-style:italic;font-size:19px;font-weight:1000;letter-spacing:.08em;text-align:center;line-height:1.05}
.top-sub{font-size:12px;text-align:center;color:#e6edf3;margin-top:4px}
.page-title{text-align:center;font-size:25px;font-weight:1000;line-height:1.02;margin:4px 0 2px}
.page-sub{text-align:center;color:#e0e7ed;font-size:12px;margin-bottom:9px}
.section-title{font-size:18px;font-weight:1000;margin:12px 0 7px}
.small{font-size:12px;color:var(--muted);line-height:1.45}
.panel{background:linear-gradient(145deg,#0c1c2b,#06121c);border:1px solid #1c4059;border-radius:15px;padding:14px;margin:9px 0}
.panel-title{font-size:18px;font-weight:1000}.kicker{font-size:11px;font-weight:1000;letter-spacing:.11em;color:var(--lime);text-transform:uppercase}
.home-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:8px 0}
.home-card{min-height:112px;border-radius:12px;padding:12px 7px 9px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:#fff;border:1px solid #21455e;box-shadow:inset 0 0 30px rgba(0,0,0,.12)}
.home-card .icon{font-size:30px;line-height:1;margin-bottom:9px}.home-card .title{font-size:13px;font-weight:1000;line-height:1.1}.home-card .sub{font-size:10px;color:#e1e8ee;margin-top:5px}
.c-gold{background:linear-gradient(145deg,#2c2108,#0d151b);border-color:#7b5b17}.c-purple{background:linear-gradient(145deg,#25123a,#0b151e);border-color:#64359b}.c-cyan{background:linear-gradient(145deg,#082b3b,#071821);border-color:#12628b}.c-green{background:linear-gradient(145deg,#142d11,#08151a);border-color:#3f7b31}.c-yellow{background:linear-gradient(145deg,#2c2208,#0a151b);border-color:#8e6b10}.c-pink{background:linear-gradient(145deg,#31101f,#0a151b);border-color:#8f2a50}
.ask-home{display:flex;align-items:center;justify-content:space-between;background:linear-gradient(135deg,#073152,#081a2c);border:1px solid #0e5b8c;border-radius:12px;padding:15px;margin:10px 0;color:#fff}
.ask-home .ask-left{display:flex;gap:12px;align-items:center}.ask-home .ask-icon{font-size:28px}.ask-home .ask-title{font-weight:1000;font-size:15px}.ask-home .ask-sub{font-size:10px;color:#c7d8e6;margin-top:3px}
.league-card{display:flex;align-items:center;justify-content:space-between;background:linear-gradient(145deg,#0b1822,#061019);border:1px solid #1c3a50;border-radius:12px;padding:14px;margin-top:9px}
.league-name{font-weight:1000;font-size:16px}.league-sub{font-size:10px;color:#c5d0d8;margin-top:3px}.league-btn{background:linear-gradient(135deg,#7b20bc,#a72ce4);padding:12px 16px;border-radius:9px;color:#fff;font-size:11px;font-weight:1000}
[data-baseweb="select"]>div,[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,[data-testid="stTextArea"] textarea{background:#071520!important;border:1px solid #18384f!important;color:#fff!important;border-radius:9px!important;font-size:15px!important;min-height:44px!important}
[data-testid="stTextArea"] textarea{min-height:110px!important}.stButton button,div[data-testid="stFormSubmitButton"] button{min-height:44px!important;border-radius:9px!important;background:#0b1b28!important;color:#fff!important;border:1px solid #24465e!important;font-size:13px!important;font-weight:900!important}.stButton button[kind="primary"],div[data-testid="stFormSubmitButton"] button[kind="primary"]{background:linear-gradient(180deg,#dfff00,#bce900)!important;color:#101600!important;border-color:#dfff00!important}
[data-testid="stTabs"] button{font-size:12px!important;font-weight:950!important;min-height:42px!important;color:#e5edf3!important}[data-testid="stTabs"] button[aria-selected="true"]{color:var(--lime)!important;border-bottom-color:var(--lime)!important}
.pos-legend{display:flex;gap:8px;margin:8px 0 10px;overflow-x:auto}.pospill{flex:1;min-width:48px;text-align:center;padding:8px 9px;border-radius:8px;color:#fff;font-size:12px;font-weight:1000}.qb{background:linear-gradient(180deg,#d8363b,#99191e)}.rb{background:linear-gradient(180deg,#f08a0b,#bc4d00)}.wr{background:linear-gradient(180deg,#149ce8,#0964a7)}.te{background:linear-gradient(180deg,#4aba48,#247627)}.flex{background:linear-gradient(180deg,#a34be0,#632a96)}.k{background:linear-gradient(180deg,#5d6974,#323b43)}.def{background:linear-gradient(180deg,#895823,#5c3511)}
.list-head,.player-row{display:grid;grid-template-columns:38px minmax(0,1.55fr) 46px 48px 52px;align-items:center;gap:6px}.list-head{height:28px;background:#07121c;border:1px solid #163145;border-radius:8px 8px 0 0;padding:0 9px;font-size:9px;color:#d9e2ea}.player-row{min-height:42px;padding:0 9px;margin:2px 0;border-radius:8px;color:#fff;border:1px solid rgba(255,255,255,.12);font-size:11px}.player-row.QB{background:linear-gradient(90deg,#8f1c22,#bb2c31)}.player-row.RB{background:linear-gradient(90deg,#bd4d00,#ea7507)}.player-row.WR{background:linear-gradient(90deg,#075f93,#1589c7)}.player-row.TE{background:linear-gradient(90deg,#23752b,#3ea644)}.player-row.FLEX{background:linear-gradient(90deg,#5d2c8b,#8a42c1)}.player-row.K{background:#45515b}.player-row.DEF{background:#66451e}.rank-dot{width:27px;height:27px;border-radius:50%;display:grid;place-items:center;background:rgba(0,0,0,.18);font-weight:1000}.pname{font-size:12px;font-weight:1000;color:#fff!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pteam,.ppos,.padp{font-size:10px;font-weight:850}.padp{text-align:right}.draft-link{font-size:9px;color:var(--lime)!important;font-weight:1000;text-align:right}
.clock{display:flex;align-items:center;justify-content:space-between;background:#050e15;border:1px solid #17354a;border-radius:9px;padding:10px;margin-top:8px}.clock .pick{color:var(--lime);font-weight:1000}.timer{background:var(--lime);color:#111900;border-radius:8px;padding:9px 11px;font-weight:1000}
.board-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;background:#02070c;border:1px solid #173247;border-radius:10px;padding:6px}.board{display:grid;gap:3px;min-width:820px}.board-cell{min-height:58px;border-radius:4px;padding:4px;color:#fff;text-align:center;border:1px solid rgba(255,255,255,.13)}.board-cell.QB{background:#a82127}.board-cell.RB{background:#cf5e04}.board-cell.WR{background:#0b73ad}.board-cell.TE{background:#2d8833}.board-cell.FLEX{background:#6f3aa0}.board-cell.K{background:#46515a}.board-cell.DEF{background:#6a481e}.board-empty{background:#08131d!important;opacity:.35}.board-rnd{font-size:7px;opacity:.8}.board-player{font-size:8px;font-weight:1000;line-height:1.05;margin-top:4px}.board-pos{font-size:8px;margin-top:3px}
.profile-top{background:linear-gradient(145deg,#0a1b28,#06121b);border:1px solid #1c3b51;border-radius:12px;padding:12px;margin:8px 0}.profile-name{text-align:center;font-size:24px;font-weight:1000}.profile-meta{text-align:center;font-size:11px;color:#d4dce3;margin-top:2px}.profile-main{display:grid;grid-template-columns:98px 1fr;gap:10px;align-items:center;margin-top:10px}.avatar{height:105px;border-radius:8px;background:radial-gradient(circle at 50% 35%,#2c6081,#0b2030 70%);display:flex;align-items:center;justify-content:center;font-size:38px;font-weight:1000;color:#d7ff00;border:1px solid #24506b}.profile-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:5px}.stat{text-align:center}.stat-v{font-size:19px;font-weight:1000;color:#ffb31a}.stat-v.rank{color:#ff4056}.stat-l{font-size:8px;color:#aebbc6;margin-top:2px;font-weight:900}.bio-row{display:flex;justify-content:space-between;margin-top:8px;padding:7px 8px;border-radius:7px;background:#07141e;font-size:9px;color:#d9e1e7}.season-pills{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin:8px 0}.season-pill{background:#0c1b28;border:1px solid #24445a;border-radius:7px;padding:7px 4px;text-align:center;color:#fff;font-size:10px;font-weight:900}.season-pill.active{background:#067cc0;border-color:#149ee9}.week-head,.week-row{display:grid;grid-template-columns:28px 42px 66px 44px 42px 38px 48px 28px;gap:4px;align-items:center}.week-head{font-size:8px;color:#c8d1d9;padding:5px 4px;border-bottom:1px solid #1b3547}.week-row{font-size:9px;padding:6px 4px;border-bottom:1px solid #152c3c}.fpts{color:#31d4ff;font-weight:1000}
.bottom-nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:min(100%,520px);z-index:60;background:rgba(2,7,12,.97);border-top:1px solid #173247;padding:7px 10px 9px;backdrop-filter:blur(12px)}.bottom-grid{display:grid;grid-template-columns:repeat(5,1fr)}.bn{text-align:center;color:#c7d2da;font-size:9px}.bn .ico{display:block;font-size:18px;margin-bottom:2px}.bn.active{color:var(--lime);font-weight:1000}.answer{background:#0b2437;border:1px solid #1d506e;border-left:4px solid var(--lime);border-radius:10px;padding:13px;font-size:13px;line-height:1.48;margin-top:9px}
@media(max-width:390px){.block-container{padding-left:9px!important;padding-right:9px!important}.home-grid{gap:7px}.home-card{min-height:105px}.home-card .title{font-size:12px}.player-row{grid-template-columns:34px minmax(0,1.45fr) 42px 42px 48px}.pname{font-size:11px}.profile-main{grid-template-columns:88px 1fr}.stat-v{font-size:17px}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

if "_splash_seen" not in st.session_state:
    try:
        splash_b64 = SPLASH_PATH.read_text(encoding="utf-8").strip()
        st.markdown(f'<div class="shiva-splash"><img src="data:image/jpeg;base64,{splash_b64}" alt="Shiva Intelligence loading screen"></div>', unsafe_allow_html=True)
    except Exception:
        pass
    st.session_state["_splash_seen"] = True

@st.cache_data(show_spinner=False)
def load_rankings() -> pd.DataFrame:
    df = pd.read_csv(RANKINGS_PATH)
    for c in ["adp", "consensus_adp", "overall_rank", "position_rank", "bye"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "team" not in df.columns:
        df["team"] = "—"
    df["position"] = df["position"].astype(str).str.upper().str.strip()
    return df.dropna(subset=["player_name", "position"]).sort_values(["adp", "overall_rank"], na_position="last").reset_index(drop=True)

@st.cache_data(show_spinner=False)
def history_frame() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    try:
        with sqlite3.connect(DB_PATH) as con:
            return pd.read_sql_query("SELECT * FROM draft_roi_scores", con)
    except Exception:
        return pd.DataFrame()

def norm(v: str) -> str:
    s = unicodedata.normalize("NFKD", str(v or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)

@st.cache_data(show_spinner=False, ttl=3600)
def weekly_season(season: int) -> pd.DataFrame:
    url = f"https://github.com/nflverse/nflverse-data/releases/download/player_stats/stats_player_week_{int(season)}.csv"
    try:
        df = pd.read_csv(url, low_memory=False)
    except Exception:
        return pd.DataFrame()
    name_col = next((c for c in ["player_display_name", "player_name", "display_name", "name"] if c in df.columns), None)
    if not name_col:
        return pd.DataFrame()
    df["_name_key"] = df[name_col].map(norm)
    return df

def secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.getenv(name, default)

def api_key() -> str:
    return secret("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))

def init_state():
    defaults: dict[str, Any] = {"page": "Home", "watchlist": [], "draft": None, "last_answer": "", "selected_player": "", "profile_return": "Home"}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

rankings = load_rankings()
history = history_frame()
init_state()

def go(page: str):
    st.session_state.page = page
    st.rerun()

def open_profile(name: str, return_page: str | None = None):
    st.session_state.selected_player = str(name)
    st.session_state.profile_return = return_page or st.session_state.page
    st.session_state.page = "Player Profile"
    st.rerun()

try:
    nav = st.query_params.get("nav", "")
    player = st.query_params.get("player", "")
    draft_player = st.query_params.get("draft_player", "")
except Exception:
    nav = player = draft_player = ""

if nav:
    st.session_state.page = str(nav)
    try: st.query_params.clear()
    except Exception: pass
    st.rerun()
if player:
    st.session_state.selected_player = str(player)
    st.session_state.profile_return = st.session_state.page
    st.session_state.page = "Player Profile"
    try: st.query_params.clear()
    except Exception: pass
    st.rerun()

def topbar(title: str = "SHIVA INTELLIGENCE", subtitle: str = "Your Draft Command Center"):
    st.markdown(f'<div class="topbar"><div class="top-brand">{title}</div><div class="top-sub">{subtitle}</div></div>', unsafe_allow_html=True)

def bottom_nav(active: str):
    items = [("⌂", "Home", "Home"), ("◉", "Draft", "Mock Draft"), ("♙", "Players", "Players"), ("♧", "Team", "Team"), ("•••", "More", "Draft Coach")]
    html = '<div class="bottom-nav"><div class="bottom-grid">'
    for ico, label, page in items:
        cls = "bn active" if label == active else "bn"
        html += f'<a class="{cls}" href="?nav={quote(page)}"><span class="ico">{ico}</span>{label}</a>'
    st.markdown(html + '</div></div>', unsafe_allow_html=True)

def history_summary() -> str:
    return "Historical league database unavailable." if history.empty else f"{len(history):,} verified historical draft rows."

def draft_context() -> dict | None:
    d = st.session_state.draft
    if not d: return None
    cfg = d["config"]
    avail = available_players(rankings, d["picks"]).head(30)
    cols = [c for c in ["player_name", "position", "team", "adp", "position_rank"] if c in avail.columns]
    return {"teams": cfg["teams"], "rounds": cfg["rounds"], "user_slot": cfg["user_slot"], "scoring": cfg["scoring"], "next_pick": d["next_pick"], "user_roster": user_roster(d["picks"], cfg["user_slot"]), "roster_counts": roster_counts(d["picks"], cfg["user_slot"]), "top_available": avail[cols].where(pd.notna(avail), None).to_dict("records"), "watchlist": st.session_state.watchlist}

def position_legend():
    st.markdown('<div class="pos-legend"><span class="pospill qb">QB</span><span class="pospill rb">RB</span><span class="pospill wr">WR</span><span class="pospill te">TE</span><span class="pospill flex">FLEX</span><span class="pospill k">K</span><span class="pospill def">DEF</span></div>', unsafe_allow_html=True)

def pos_class(pos: str) -> str:
    p = str(pos).upper()
    return p if p in {"QB", "RB", "WR", "TE", "FLEX", "K", "DEF"} else "FLEX"

def player_row_html(row, rank: int, draftable: bool = False) -> str:
    pos = str(row.get("position", "")).upper(); team = str(row.get("team", "—")); adp = "—" if pd.isna(row.get("adp")) else f"{float(row.get('adp')):.1f}"; name = str(row.get("player_name", ""))
    action = f'<a class="draft-link" href="?draft_player={quote(name)}">DRAFT</a>' if draftable else f'<span class="padp">{adp}</span>'
    return f'<div class="player-row {pos_class(pos)}"><div class="rank-dot">{rank}</div><div><a class="pname" href="?player={quote(name)}">{name}</a></div><div class="ppos">{pos}</div><div class="pteam">{team}</div><div>{action}</div></div>'

def render_home():
    topbar()
    cards = [("🏆", "DRAFT BOARD", "2026 Rankings", "Draft Board", "c-gold"), ("👥", "MOCK DRAFT", "Practice & Plan", "Mock Draft", "c-purple"), ("👤", "PLAYER PROFILES", "Stats & Trends", "Players", "c-cyan"), ("🛡️", "MY TEAM HQ", "Roster & Lineup", "Team", "c-green"), ("🥷", "SLEEPERS", "Hidden Gems", "Sleepers", "c-yellow"), ("📋", "CHEAT SHEETS", "Key Rankings", "Draft Coach", "c-pink")]
    html = '<div class="home-grid">'
    for icon, title, sub, page, cls in cards:
        html += f'<a href="?nav={quote(page)}" class="home-card {cls}"><div class="icon">{icon}</div><div class="title">{title}</div><div class="sub">{sub}</div></a>'
    st.markdown(html + '</div>', unsafe_allow_html=True)
    st.markdown('<a href="?nav=Ask%20Shiva" class="ask-home"><div class="ask-left"><div class="ask-icon">🤖</div><div><div class="ask-title">ASK SHIVA GPT</div><div class="ask-sub">Ask questions, get advice, win your league.</div></div></div><div style="font-size:26px">→</div></a>', unsafe_allow_html=True)
    st.markdown('<div class="league-card"><div><div class="small">MY LEAGUE</div><div class="league-name">Shiva Champion League</div><div class="league-sub">10-Team PPR</div></div><a class="league-btn" href="?nav=Team">VIEW LEAGUE</a></div>', unsafe_allow_html=True)
    bottom_nav("Home")

def render_rankings():
    topbar("DRAFT BOARD", "2026 Rankings")
    q = st.text_input("Search players", placeholder="Search players...", label_visibility="collapsed")
    pos = st.selectbox("Position", ["ALL", "QB", "RB", "WR", "TE"], label_visibility="collapsed")
    position_legend(); board = rankings.copy()
    if pos != "ALL": board = board[board.position.eq(pos)]
    if q: board = board[board.player_name.astype(str).str.contains(q, case=False, na=False)]
    st.markdown('<div class="list-head"><div>RK</div><div>PLAYER</div><div>POS</div><div>TEAM</div><div style="text-align:right">ADP</div></div>', unsafe_allow_html=True)
    for i, (_, r) in enumerate(board.head(55).iterrows(), 1): st.markdown(player_row_html(r, i, False), unsafe_allow_html=True)
    bottom_nav("Draft")

def render_players():
    topbar("PLAYER PROFILES", "Stats & Trends")
    q = st.text_input("Search player", placeholder="Search players...", label_visibility="collapsed")
    pos = st.selectbox("Position", ["ALL", "QB", "RB", "WR", "TE"], label_visibility="collapsed", key="players_pos")
    frame = rankings.copy()
    if pos != "ALL": frame = frame[frame.position.eq(pos)]
    if q: frame = frame[frame.player_name.astype(str).str.contains(q, case=False, na=False)]
    st.markdown('<div class="list-head"><div>RK</div><div>PLAYER</div><div>POS</div><div>TEAM</div><div style="text-align:right">ADP</div></div>', unsafe_allow_html=True)
    for i, (_, r) in enumerate(frame.head(55).iterrows(), 1): st.markdown(player_row_html(r, i, False), unsafe_allow_html=True)
    bottom_nav("Players")

def render_profile(name: str):
    if st.button("‹ Back", key="profile_back"): go(st.session_state.get("profile_return", "Players"))
    found = rankings[rankings.player_name.astype(str).eq(str(name))]
    if found.empty:
        st.error("Player not found."); bottom_nav("Players"); return
    r = found.iloc[0]; pos = str(r.position); team = str(r.team); pr = f"{pos}{int(r.position_rank)}" if pd.notna(r.position_rank) else pos
    st.markdown(f'<div class="profile-name">{name.upper()}</div><div class="profile-meta">{pos} • {team}</div>', unsafe_allow_html=True)
    tabs = st.tabs(["OVERVIEW", "STATS", "GAME LOG", "NEWS"])
    with tabs[0]:
        season = st.selectbox("Season", list(range(2025, 2013, -1)), index=0, key=f"season_{norm(name)}")
        weekly = weekly_season(int(season))
        if not weekly.empty:
            weekly = weekly[weekly["_name_key"].eq(norm(name))].copy()
            if "season_type" in weekly.columns:
                reg = weekly[weekly.season_type.astype(str).str.upper().eq("REG")]
                if not reg.empty: weekly = reg
        fp_col = "fantasy_points_ppr" if "fantasy_points_ppr" in weekly.columns else ("fantasy_points" if "fantasy_points" in weekly.columns else None)
        pts = pd.to_numeric(weekly[fp_col], errors="coerce").fillna(0) if fp_col and not weekly.empty else pd.Series(dtype=float)
        total = float(pts.sum()) if len(pts) else 0.0; ppg = float(pts.mean()) if len(pts) else 0.0; games = len(weekly); initials = ''.join([x[0] for x in str(name).split()[:2]]).upper()
        st.markdown(f'<div class="profile-top"><div class="profile-main"><div class="avatar">{initials}</div><div class="profile-stats"><div class="stat"><div class="stat-v">{total:.1f}</div><div class="stat-l">FPTS</div></div><div class="stat"><div class="stat-v">{ppg:.1f}</div><div class="stat-l">PPG</div></div><div class="stat"><div class="stat-v">{games}</div><div class="stat-l">GAMES</div></div><div class="stat"><div class="stat-v rank">{pr}</div><div class="stat-l">RANK</div></div></div></div><div class="bio-row"><span>Team: {team}</span><span>Position: {pos}</span><span>2026 ADP: {"—" if pd.isna(r.adp) else f"{float(r.adp):.1f}"}</span></div></div>', unsafe_allow_html=True)
        active = int(season); st.markdown('<div class="season-pills">' + ''.join(f'<div class="season-pill {"active" if y==active else ""}">{y}</div>' for y in [2025,2024,2023,2022,2021]) + '</div>', unsafe_allow_html=True)
        if weekly.empty or not fp_col: st.info(f"No weekly {season} data found for {name}.")
        else:
            if "week" in weekly.columns:
                weekly["week"] = pd.to_numeric(weekly["week"], errors="coerce"); weekly = weekly.sort_values("week")
            opp_col = next((c for c in ["opponent_team", "opponent", "opp"] if c in weekly.columns), None)
            st.markdown('<div class="week-head"><div>WK</div><div>OPP</div><div>RESULT</div><div>FPTS</div><div>RUSH</div><div>REC</div><div>REC YDS</div><div>TD</div></div>', unsafe_allow_html=True)
            for _, w in weekly.iterrows():
                def num(c, default=0): return float(pd.to_numeric(pd.Series([w.get(c, default)]), errors="coerce").fillna(default).iloc[0])
                wk = int(num("week")); opp = str(w.get(opp_col, "—")) if opp_col else "—"; fpts = num(fp_col); rush = int(num("rushing_yards")); rec = int(num("receptions")); recyd = int(num("receiving_yards")); td = int(num("passing_tds") + num("rushing_tds") + num("receiving_tds")); result = str(w.get("result", "—")) if "result" in weekly.columns else "—"
                st.markdown(f'<div class="week-row"><div>{wk}</div><div>{opp}</div><div>{result}</div><div class="fpts">{fpts:.1f}</div><div>{rush}</div><div>{rec}</div><div>{recyd}</div><div>{td}</div></div>', unsafe_allow_html=True)
    with tabs[1]: st.caption("Season totals and draft rank are shown on Overview for faster draft-day scanning.")
    with tabs[2]: st.caption("The complete weekly game log is shown on Overview.")
    with tabs[3]: st.caption("Live news can be connected to a news feed in a later pass.")
    bottom_nav("Players")

def render_ask():
    topbar("ASK SHIVA GPT", "Draft Intelligence")
    st.markdown('<div class="panel"><div class="kicker">SHIVA AI</div><div class="panel-title">Ask anything about your draft.</div><div class="small">Your current rankings, watch list and live mock state are sent with the question.</div></div>', unsafe_allow_html=True)
    with st.form("ask_form"):
        q = st.text_area("What do you want to know?", placeholder="I started RB-RB. Who should I target at 3.04?", height=115)
        submit = st.form_submit_button("ASK SHIVA GPT", use_container_width=True, type="primary")
    if submit and q.strip():
        if not api_key(): st.warning("Add OPENAI_API_KEY in Streamlit → App Settings → Secrets to activate Shiva GPT.")
        else:
            context = build_context(rankings=rankings, watchlist=st.session_state.watchlist, draft=draft_context(), history_summary=history_summary())
            try:
                with st.spinner("Shiva is analyzing..."): st.session_state.last_answer = ask_shiva(api_key(), secret("OPENAI_MODEL", MODEL), q.strip(), context)
            except Exception as exc: st.error(f"Shiva API error: {exc}")
    if st.session_state.last_answer: st.markdown(f'<div class="answer">{st.session_state.last_answer}</div>', unsafe_allow_html=True)
    bottom_nav("Home")

def render_team():
    topbar("MY TEAM HQ", "Roster & Watch List")
    selected = st.multiselect("Watch List", rankings.player_name.tolist(), default=st.session_state.watchlist, placeholder="Add favorite players"); st.session_state.watchlist = selected
    frame = rankings[rankings.player_name.isin(selected)].sort_values("adp") if selected else pd.DataFrame()
    if frame.empty: st.markdown('<div class="panel"><div class="panel-title">⭐ Watch List</div><div class="small">Add favorite players above. They will stay visible during mocks and be included in Shiva GPT context.</div></div>', unsafe_allow_html=True)
    else:
        for i, (_, r) in enumerate(frame.iterrows(), 1): st.markdown(player_row_html(r, i, False), unsafe_allow_html=True)
    bottom_nav("Team")

def render_sleepers():
    topbar("SLEEPERS", "Hidden Gems")
    frame = rankings[(rankings.adp >= 45) & rankings.position.isin(["QB", "RB", "WR", "TE"])].head(40)
    st.markdown('<div class="panel"><div class="panel-title">2026 Value Board</div><div class="small">Mid- and late-round targets by current ADP. Tap any name for the full player profile.</div></div>', unsafe_allow_html=True)
    for i, (_, r) in enumerate(frame.iterrows(), 1): st.markdown(player_row_html(r, i, False), unsafe_allow_html=True)
    bottom_nav("More")

def render_draft_coach():
    topbar("CHEAT SHEETS", "Draft Plan")
    st.markdown('<div class="panel"><div class="panel-title">2026 Draft Plan</div><div class="small">Use the ranking board, mock room and Shiva GPT together. This page is reserved for your saved round-by-round draft plan.</div></div>', unsafe_allow_html=True)
    if st.button("OPEN DRAFT BOARD", use_container_width=True): go("Draft Board")
    if st.button("OPEN MOCK DRAFT", use_container_width=True): go("Mock Draft")
    bottom_nav("More")

def process_draft_player():
    global draft_player
    if not draft_player or not st.session_state.draft: return
    d = st.session_state.draft; cfg = DraftConfig(**d["config"])
    if d["next_pick"] <= cfg.teams * cfg.rounds and pick_team(d["next_pick"], cfg.teams) == cfg.user_slot:
        match = rankings[rankings.player_name.astype(str).eq(str(draft_player))]
        if not match.empty and str(draft_player) not in {p["player_name"] for p in d["picks"]}:
            d["picks"].append(make_pick(match.iloc[0].to_dict(), d["next_pick"], cfg.teams)); d["next_pick"] += 1; d["picks"], d["next_pick"] = advance_cpus(rankings, d["picks"], d["next_pick"], cfg); st.session_state.draft = d
    try: st.query_params.clear()
    except Exception: pass
    st.rerun()

def render_mock():
    topbar("MOCK DRAFT", "10-Team PPR • Snake Draft")
    if not st.session_state.draft:
        st.markdown('<div class="panel"><div class="panel-title">Start a Mock Draft</div><div class="small">Set your league, slot and rounds. CPU managers draft from current ADP.</div></div>', unsafe_allow_html=True)
        with st.form("mock_setup"):
            c1, c2 = st.columns(2)
            with c1: teams = st.selectbox("Teams", [10, 12])
            with c2: slot = st.number_input("Draft Position", 1, 12, 4, 1)
            c3, c4 = st.columns(2)
            with c3: rounds = st.selectbox("Rounds", [15, 16, 17, 18], index=1)
            with c4: scoring = st.selectbox("Scoring", ["PPR", "Half PPR", "Standard"])
            start = st.form_submit_button("START MOCK DRAFT", use_container_width=True, type="primary")
        if start:
            slot = min(int(slot), int(teams)); cfg = DraftConfig(teams=int(teams), rounds=int(rounds), user_slot=slot, scoring=scoring); picks: list[dict] = []; picks, next_pick = advance_cpus(rankings, picks, 1, cfg); st.session_state.draft = {"config": cfg.__dict__, "picks": picks, "next_pick": next_pick}; st.rerun()
        bottom_nav("Draft"); return
    process_draft_player(); d = st.session_state.draft; cfg = DraftConfig(**d["config"]); total = cfg.teams * cfg.rounds; done = d["next_pick"] > total
    tabs = st.tabs(["DRAFT BOARD", "QUEUE", "TEAM", "RESULTS"])
    with tabs[0]:
        q = st.text_input("Search", placeholder="Search players...", label_visibility="collapsed", key="mock_search"); pos = st.selectbox("All Positions", ["ALL", "QB", "RB", "WR", "TE"], label_visibility="collapsed", key="mock_pos"); position_legend(); avail = score_board(rankings, d["picks"], cfg.user_slot, d["next_pick"])
        if pos != "ALL": avail = avail[avail.position.eq(pos)]
        if q: avail = avail[avail.player_name.astype(str).str.contains(q, case=False, na=False)]
        st.markdown('<div class="list-head"><div>RK</div><div>PLAYER</div><div>POS</div><div>TEAM</div><div style="text-align:right">PICK</div></div>', unsafe_allow_html=True)
        for i, (_, r) in enumerate(avail.head(35).iterrows(), 1): st.markdown(player_row_html(r, i, draftable=not done), unsafe_allow_html=True)
        pick_text = "DRAFT COMPLETE" if done else f"Pick {d['next_pick']}"; st.markdown(f'<div class="clock"><div><div style="font-size:10px">You’re on the clock!</div><div class="pick">{pick_text}</div></div><div style="font-weight:900">Team {cfg.user_slot}</div><div class="timer">01:30</div></div>', unsafe_allow_html=True)
    with tabs[1]:
        qdf = rankings[rankings.player_name.isin(st.session_state.watchlist)].sort_values("adp")
        if qdf.empty: st.info("Your watch list is your draft queue. Add players in My Team HQ.")
        for i, (_, r) in enumerate(qdf.iterrows(), 1): st.markdown(player_row_html(r, i, False), unsafe_allow_html=True)
    with tabs[2]:
        roster = user_roster(d["picks"], cfg.user_slot)
        if not roster: st.info("No players drafted yet.")
        else:
            for i, pick in enumerate(roster, 1):
                match = rankings[rankings.player_name.astype(str).eq(str(pick.get("player_name", "")))]
                if not match.empty: st.markdown(player_row_html(match.iloc[0], i, False), unsafe_allow_html=True)
    with tabs[3]:
        position_legend(); matrix = board_matrix(d["picks"], cfg.teams, cfg.rounds); cells = []
        for rnd, row in enumerate(matrix, 1):
            for team, pick in enumerate(row, 1):
                if pick:
                    p = pos_class(str(pick.get("position", ""))); name = str(pick.get("player_name", "")); cells.append(f'<div class="board-cell {p}"><div class="board-rnd">R{rnd} · T{team}</div><div class="board-player">{name}</div><div class="board-pos">{p}</div></div>')
                else: cells.append(f'<div class="board-cell board-empty"><div class="board-rnd">R{rnd} · T{team}</div><div class="board-player">—</div></div>')
        st.markdown(f'<div class="board-wrap"><div class="board" style="grid-template-columns:repeat({cfg.teams},minmax(76px,1fr))">{"".join(cells)}</div></div>', unsafe_allow_html=True)
        if st.button("RESET DRAFT", use_container_width=True): st.session_state.draft = None; st.rerun()
    bottom_nav("Draft")

page = st.session_state.page
if page == "Home": render_home()
elif page == "Draft Board": render_rankings()
elif page == "Players": render_players()
elif page == "Player Profile": render_profile(st.session_state.selected_player)
elif page == "Mock Draft": render_mock()
elif page == "Ask Shiva": render_ask()
elif page == "Team": render_team()
elif page == "Sleepers": render_sleepers()
elif page == "Draft Coach": render_draft_coach()
else: render_home()
