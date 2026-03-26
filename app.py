"""
NCAA March Madness Survivor Pool Engine v5
==========================================
Multi-contest survivor pool tracker with opponent modeling,
leverage/safety recommendations, and live game tracking.

Contests:
  - Sleeping Beauty (1,815 entries)
  - Splash Contest (TBD - awaiting data)
"""

import streamlit as st
import json
import math
from datetime import datetime, date
from collections import OrderedDict

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Survivor Pool Engine v5",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0a0e1a; }
    
    /* Headers */
    h1, h2, h3 { color: #e8e8e8 !important; }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #111827;
    }
    
    /* Metric cards */
    [data-testid="stMetric"] {
        background-color: #1a1f35;
        border: 1px solid #2a3050;
        border-radius: 10px;
        padding: 12px 16px;
    }
    [data-testid="stMetricValue"] { color: #60a5fa !important; }
    [data-testid="stMetricLabel"] { color: #9ca3af !important; }
    
    /* Alive badge */
    .alive-badge {
        display: inline-block;
        background: linear-gradient(135deg, #065f46, #047857);
        color: #6ee7b7;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.85em;
        margin-left: 8px;
    }
    .dead-badge {
        display: inline-block;
        background: linear-gradient(135deg, #7f1d1d, #991b1b);
        color: #fca5a5;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.85em;
        margin-left: 8px;
    }
    
    /* Pick cards */
    .pick-card {
        background: #1e2640;
        border-radius: 10px;
        padding: 14px 18px;
        margin: 6px 0;
        border-left: 4px solid #3b82f6;
    }
    .pick-card.win { border-left-color: #10b981; background: #0f2a1e; }
    .pick-card.loss { border-left-color: #ef4444; background: #2a1010; }
    .pick-card.pending { border-left-color: #f59e0b; background: #2a2210; }
    
    /* Opponent table */
    .opp-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        border-bottom: 1px solid #1e2640;
        font-size: 0.92em;
    }
    .opp-row:hover { background: #1a1f35; }
    .opp-team { color: #e0e0e0; font-weight: 600; min-width: 180px; }
    .opp-pct { color: #60a5fa; font-weight: 700; min-width: 60px; text-align: right; }
    .opp-count { color: #9ca3af; min-width: 60px; text-align: right; }
    .opp-result { min-width: 30px; text-align: center; font-size: 1.1em; }
    
    /* Bar chart inline */
    .bar-bg {
        height: 10px;
        background: #1e2640;
        border-radius: 5px;
        flex-grow: 1;
        margin: 0 12px;
        min-width: 80px;
    }
    .bar-fill-green {
        height: 10px;
        background: linear-gradient(90deg, #10b981, #34d399);
        border-radius: 5px;
    }
    .bar-fill-red {
        height: 10px;
        background: linear-gradient(90deg, #ef4444, #f87171);
        border-radius: 5px;
    }
    .bar-fill-yellow {
        height: 10px;
        background: linear-gradient(90deg, #f59e0b, #fbbf24);
        border-radius: 5px;
    }
    
    /* Leverage highlight */
    .leverage-tag {
        display: inline-block;
        background: #312e81;
        color: #a5b4fc;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75em;
        font-weight: 600;
    }
    .safety-tag {
        display: inline-block;
        background: #064e3b;
        color: #6ee7b7;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75em;
        font-weight: 600;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1f35;
        border-radius: 8px 8px 0 0;
        color: #9ca3af;
        padding: 8px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e3a5f !important;
        color: #60a5fa !important;
    }
    
    /* Divider */
    hr { border-color: #2a3050 !important; }
    
    /* Expander */
    .streamlit-expanderHeader { color: #e0e0e0 !important; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# DATA: Tournament Results & Opponent Picks
# ═══════════════════════════════════════════════════════════════════════════════

# Complete R64 + R32 results from Thursday-Saturday 2026
GAME_RESULTS = {
    # Thursday R64 - Winners
    "Nebraska": {"seed": 4, "won_r64": True, "won_r32": True, "r64_opponent": "Troy", "r32_opponent": "Vanderbilt", "alive": True},
    "Wisconsin": {"seed": 5, "won_r64": False, "r64_opponent": "High Point", "alive": False, "lost_day": "Thursday"},
    "Arkansas": {"seed": 4, "won_r64": True, "won_r32": True, "r64_opponent": "Hawai'i", "r32_opponent": "High Point", "alive": True},
    "Vanderbilt": {"seed": 5, "won_r64": True, "won_r32": False, "r64_opponent": "McNeese", "r32_opponent": "Nebraska", "alive": False, "lost_day": "Saturday"},
    "Gonzaga": {"seed": 3, "won_r64": True, "won_r32": False, "r64_opponent": "Kennesaw St", "r32_opponent": "Texas", "alive": False, "lost_day": "Saturday"},
    "Illinois": {"seed": 3, "won_r64": True, "won_r32": True, "r64_opponent": "Penn", "r32_opponent": "VCU", "alive": True},
    "Michigan State": {"seed": 3, "won_r64": True, "won_r32": True, "r64_opponent": "North Dakota St", "r32_opponent": "Louisville", "alive": True},
    "St. Mary's": {"seed": 7, "won_r64": False, "r64_opponent": "Texas A&M", "alive": False, "lost_day": "Thursday"},
    "BYU": {"seed": 6, "won_r64": False, "r64_opponent": "Texas", "alive": False, "lost_day": "Thursday"},
    "North Carolina": {"seed": 6, "won_r64": False, "r64_opponent": "VCU", "alive": False, "lost_day": "Thursday"},
    "Ohio State": {"seed": 8, "won_r64": False, "r64_opponent": "TCU", "alive": False, "lost_day": "Thursday"},
    "Louisville": {"seed": 6, "won_r64": True, "won_r32": False, "r64_opponent": "South Florida", "r32_opponent": "Michigan State", "alive": False, "lost_day": "Saturday"},
    "Georgia": {"seed": 8, "won_r64": False, "r64_opponent": "St. Louis", "alive": False, "lost_day": "Thursday"},
    "VCU": {"seed": 11, "won_r64": True, "won_r32": False, "r64_opponent": "North Carolina", "r32_opponent": "Illinois", "alive": False, "lost_day": "Saturday"},
    "St. Louis": {"seed": 9, "won_r64": True, "won_r32": False, "r64_opponent": "Georgia", "r32_opponent": "Michigan", "alive": False, "lost_day": "Saturday"},
    "Houston": {"seed": 2, "won_r64": True, "won_r32": True, "r64_opponent": "Idaho", "r32_opponent": "Texas A&M", "alive": True},
    "South Florida": {"seed": 11, "won_r64": False, "r64_opponent": "Louisville", "alive": False, "lost_day": "Thursday"},
    "TCU": {"seed": 9, "won_r64": True, "won_r32": False, "r64_opponent": "Ohio State", "r32_opponent": "Duke", "alive": False, "lost_day": "Saturday"},
    "Duke": {"seed": 1, "won_r64": True, "won_r32": True, "r64_opponent": "Siena", "r32_opponent": "TCU", "alive": True},
    "Texas A&M": {"seed": 10, "won_r64": True, "won_r32": False, "r64_opponent": "St. Mary's", "r32_opponent": "Houston", "alive": False, "lost_day": "Saturday"},
    "Texas": {"seed": 11, "won_r64": True, "won_r32": True, "r64_opponent": "BYU", "r32_opponent": "Gonzaga", "alive": True},
    "Michigan": {"seed": 1, "won_r64": True, "won_r32": True, "r64_opponent": "Howard", "r32_opponent": "St. Louis", "alive": True},
    "High Point": {"seed": 12, "won_r64": True, "won_r32": False, "r64_opponent": "Wisconsin", "r32_opponent": "Arkansas", "alive": False, "lost_day": "Saturday"},
    
    # Friday R64 - all favorites won
    "Kansas": {"seed": 4, "won_r64": True, "r64_opponent": "Cal Baptist", "alive": True},
    "Virginia": {"seed": 3, "won_r64": True, "r64_opponent": "Wright State", "alive": True},
    "Alabama": {"seed": 4, "won_r64": True, "r64_opponent": "Hofstra", "alive": True},
    "St. John's": {"seed": 5, "won_r64": True, "r64_opponent": "Notre Dame/Fairfield", "alive": True},
    "Tennessee": {"seed": 6, "won_r64": True, "r64_opponent": "Utah State/Drake", "alive": True},
    "UCLA": {"seed": 7, "won_r64": True, "r64_opponent": "UCF", "alive": True},
    "Texas Tech": {"seed": 5, "won_r64": True, "r64_opponent": "Akron", "alive": True},
    "Connecticut": {"seed": 2, "won_r64": True, "r64_opponent": "Furman", "alive": True},
    "Kentucky": {"seed": 7, "won_r64": True, "r64_opponent": "Santa Clara", "alive": True},
    "Purdue": {"seed": 2, "won_r64": True, "r64_opponent": "Queens", "alive": True},
    "Iowa State": {"seed": 2, "won_r64": True, "r64_opponent": "Tennessee St", "alive": True},
    "Utah State": {"seed": 9, "won_r64": True, "r64_opponent": "Oklahoma St", "alive": True},
    "Iowa": {"seed": 9, "won_r64": True, "r64_opponent": "Clemson", "alive": True},
    "Miami": {"seed": 7, "won_r64": True, "r64_opponent": "Missouri", "alive": True},
    "Florida": {"seed": 1, "won_r64": True, "r64_opponent": "Prairie View A&M", "alive": True},
    "Arizona": {"seed": 1, "won_r64": True, "r64_opponent": "Lehigh/Howard", "alive": True},
    "Villanova": {"seed": None, "won_r64": False, "alive": False, "lost_day": "Friday"},
    "Central Florida": {"seed": None, "won_r64": False, "r64_opponent": "UCLA", "alive": False, "lost_day": "Friday"},
    "Clemson": {"seed": 8, "won_r64": False, "r64_opponent": "Iowa", "alive": False, "lost_day": "Friday"},
    "Santa Clara": {"seed": 10, "won_r64": False, "r64_opponent": "Kentucky", "alive": False, "lost_day": "Friday"},
    "Akron": {"seed": 12, "won_r64": False, "r64_opponent": "Texas Tech", "alive": False, "lost_day": "Friday"},
    "Missouri": {"seed": 10, "won_r64": False, "r64_opponent": "Miami", "alive": False, "lost_day": "Friday"},
    "Miami (Ohio)": {"seed": 13, "won_r64": False, "alive": False, "lost_day": "Friday"},
    "Northern Iowa": {"seed": None, "won_r64": False, "alive": False},
}

# Sunday R32 results (March 22, 2026) — COMPLETED
SUNDAY_RESULTS = {
    "Purdue": "W", "Miami": "L",         # Purdue beat Miami
    "Iowa State": "W", "Kentucky": "L",   # Iowa State beat Kentucky
    "St. John's": "W", "Kansas": "L",     # St. John's upset Kansas
    "Tennessee": "W", "Virginia": "L",    # Tennessee beat Virginia
    "Iowa": "W", "Florida": "L",          # Iowa upset #1 Florida!
    "Arizona": "W", "Utah State": "L",    # Arizona beat Utah State
    "Connecticut": "W", "UCLA": "L",      # UConn beat UCLA
    "Alabama": "W", "Texas Tech": "L",    # Alabama beat Texas Tech
}

# ─── Current Round: Sweet 16 (March 26-27, 2026) ────────────────────────────
CURRENT_ROUND = "Sweet 16"
CURRENT_ROUND_LABEL = "Sweet 16 · March 26-27"

NEXT_ROUND_GAMES = [
    # Thursday March 26 — SOUTH region (Houston)
    {"game": "(2) Houston vs (3) Illinois", "time": "Thu ~7:10 PM ET", "day": "Thursday",
     "teams": ["Houston", "Illinois"], "seeds": [2, 3], "region": "South"},
    {"game": "(4) Nebraska vs (9) Iowa", "time": "Thu ~9:40 PM ET", "day": "Thursday",
     "teams": ["Nebraska", "Iowa"], "seeds": [4, 9], "region": "South"},
    # Thursday March 26 — WEST region (San Jose)
    {"game": "(4) Arkansas vs (1) Arizona", "time": "Thu ~7:10 PM ET", "day": "Thursday",
     "teams": ["Arkansas", "Arizona"], "seeds": [4, 1], "region": "West"},
    {"game": "(11) Texas vs (2) Purdue", "time": "Thu ~9:40 PM ET", "day": "Thursday",
     "teams": ["Texas", "Purdue"], "seeds": [11, 2], "region": "West"},
    # Friday March 27 — EAST region (DC)
    {"game": "(1) Duke vs (5) St. John's", "time": "Fri ~7:10 PM ET", "day": "Friday",
     "teams": ["Duke", "St. John's"], "seeds": [1, 5], "region": "East"},
    {"game": "(3) Michigan St vs (2) UConn", "time": "Fri ~9:40 PM ET", "day": "Friday",
     "teams": ["Michigan State", "Connecticut"], "seeds": [3, 2], "region": "East"},
    # Friday March 27 — MIDWEST region (Chicago)
    {"game": "(1) Michigan vs (4) Alabama", "time": "Fri ~7:10 PM ET", "day": "Friday",
     "teams": ["Michigan", "Alabama"], "seeds": [1, 4], "region": "Midwest"},
    {"game": "(2) Iowa State vs (6) Tennessee", "time": "Fri ~9:40 PM ET", "day": "Friday",
     "teams": ["Iowa State", "Tennessee"], "seeds": [2, 6], "region": "Midwest"},
]

# ─── Bracket Schedule: Which day does each team play in S16 and E8? ──────────
# Thu S16 / Sat E8 = South (Houston) + West (San Jose)
# Fri S16 / Sun E8 = East (DC) + Midwest (Chicago)
# S16 matchups determine E8 pairings within each region.
BRACKET_SCHEDULE = {
    # SOUTH — Thu S16 / Sat E8 (Houston)
    "Houston":       {"region": "South",   "s16_day": "Thu", "e8_day": "Sat", "alive": True},
    "Illinois":      {"region": "South",   "s16_day": "Thu", "e8_day": "Sat", "alive": True},
    "Nebraska":      {"region": "South",   "s16_day": "Thu", "e8_day": "Sat", "alive": True},
    "Iowa":          {"region": "South",   "s16_day": "Thu", "e8_day": "Sat", "alive": True},
    # WEST — Thu S16 / Sat E8 (San Jose)
    "Arkansas":      {"region": "West",    "s16_day": "Thu", "e8_day": "Sat", "alive": True},
    "Arizona":       {"region": "West",    "s16_day": "Thu", "e8_day": "Sat", "alive": True},
    "Texas":         {"region": "West",    "s16_day": "Thu", "e8_day": "Sat", "alive": True},
    "Purdue":        {"region": "West",    "s16_day": "Thu", "e8_day": "Sat", "alive": True},
    # EAST — Fri S16 / Sun E8 (DC)
    "Duke":          {"region": "East",    "s16_day": "Fri", "e8_day": "Sun", "alive": True},
    "St. John's":    {"region": "East",    "s16_day": "Fri", "e8_day": "Sun", "alive": True},
    "Michigan State": {"region": "East",   "s16_day": "Fri", "e8_day": "Sun", "alive": True},
    "Connecticut":   {"region": "East",    "s16_day": "Fri", "e8_day": "Sun", "alive": True},
    # MIDWEST — Fri S16 / Sun E8 (Chicago)
    "Michigan":      {"region": "Midwest", "s16_day": "Fri", "e8_day": "Sun", "alive": True},
    "Alabama":       {"region": "Midwest", "s16_day": "Fri", "e8_day": "Sun", "alive": True},
    "Iowa State":    {"region": "Midwest", "s16_day": "Fri", "e8_day": "Sun", "alive": True},
    "Tennessee":     {"region": "Midwest", "s16_day": "Fri", "e8_day": "Sun", "alive": True},
}

# E8 pairings (within each region, S16 winners meet):
# South E8: Houston/Illinois winner vs Nebraska/Iowa winner
# West E8: Arkansas/Arizona winner vs Texas/Purdue winner
# East E8: Duke/StJohns winner vs MichSt/UConn winner
# Midwest E8: Michigan/Alabama winner vs IowaState/Tennessee winner

# ─── Opponent Pick Data from Screenshots (Sleeping Beauty - 1,815 entries) ───

SLEEPING_BEAUTY = {
    "name": "Sleeping Beauty",
    "total_entries": 1815,
    "survivor_snapshots": {"Thursday": None, "Friday": None, "Saturday": None, "Sunday": 764},
    "days": {
        "Thursday": {
            "round": "R64",
            "date": "2026-03-19",
            "picks": OrderedDict([
                ("Nebraska", {"count": 314, "pct": 0.17, "result": "W"}),
                ("Wisconsin", {"count": 232, "pct": 0.13, "result": "L"}),
                ("Arkansas", {"count": 197, "pct": 0.11, "result": "W"}),
                ("Vanderbilt", {"count": 187, "pct": 0.10, "result": "W"}),
                ("Gonzaga", {"count": 162, "pct": 0.09, "result": "W"}),
                ("Illinois", {"count": 97, "pct": 0.05, "result": "W"}),
                ("Michigan State", {"count": 83, "pct": 0.05, "result": "W"}),
                ("St. Mary's", {"count": 83, "pct": 0.05, "result": "L"}),
                ("BYU", {"count": 72, "pct": 0.04, "result": "L"}),
                ("North Carolina", {"count": 67, "pct": 0.04, "result": "L"}),
                ("Ohio State", {"count": 66, "pct": 0.04, "result": "L"}),
                ("Louisville", {"count": 59, "pct": 0.03, "result": "W"}),
                ("Georgia", {"count": 38, "pct": 0.02, "result": "L"}),
                ("VCU", {"count": 29, "pct": 0.02, "result": "W"}),
                ("St. Louis", {"count": 27, "pct": 0.01, "result": "W"}),
                ("Houston", {"count": 24, "pct": 0.01, "result": "W"}),
                ("South Florida", {"count": 23, "pct": 0.01, "result": "L"}),
                ("TCU", {"count": 20, "pct": 0.01, "result": "W"}),
                ("Duke", {"count": 12, "pct": 0.01, "result": "W"}),
                ("Texas A&M", {"count": 9, "pct": 0.01, "result": "W"}),
                ("Texas", {"count": 7, "pct": 0.00, "result": "W"}),
                ("Michigan", {"count": 7, "pct": 0.00, "result": "W"}),
            ]),
        },
        "Friday": {
            "round": "R64",
            "date": "2026-03-20",
            "picks": OrderedDict([
                ("Kansas", {"count": 283, "pct": 0.23, "result": "W"}),
                ("Virginia", {"count": 153, "pct": 0.12, "result": "W"}),
                ("Alabama", {"count": 146, "pct": 0.12, "result": "W"}),
                ("St. John's", {"count": 128, "pct": 0.10, "result": "W"}),
                ("Tennessee", {"count": 116, "pct": 0.09, "result": "W"}),
                ("UCLA", {"count": 65, "pct": 0.05, "result": "W"}),
                ("Texas Tech", {"count": 58, "pct": 0.05, "result": "W"}),
                ("Connecticut", {"count": 51, "pct": 0.04, "result": "W"}),
                ("Kentucky", {"count": 45, "pct": 0.04, "result": "W"}),
                ("Purdue", {"count": 38, "pct": 0.03, "result": "W"}),
                ("Iowa State", {"count": 28, "pct": 0.02, "result": "W"}),
                ("Utah State", {"count": 27, "pct": 0.02, "result": "W"}),
                ("Iowa", {"count": 19, "pct": 0.02, "result": "W"}),
                ("Miami", {"count": 16, "pct": 0.01, "result": "W"}),
                ("Florida", {"count": 9, "pct": 0.01, "result": "W"}),
                ("Villanova", {"count": 8, "pct": 0.01, "result": "L"}),
                ("NO PICK", {"count": 7, "pct": 0.01, "result": "L"}),
                ("Arizona", {"count": 7, "pct": 0.01, "result": "W"}),
                ("Central Florida", {"count": 7, "pct": 0.01, "result": "L"}),
                ("Clemson", {"count": 7, "pct": 0.01, "result": "L"}),
                ("Santa Clara", {"count": 6, "pct": 0.00, "result": "L"}),
                ("Miami (Ohio)", {"count": 3, "pct": 0.00, "result": "L"}),
                ("Missouri", {"count": 3, "pct": 0.00, "result": "L"}),
                ("Akron", {"count": 3, "pct": 0.00, "result": "L"}),
                ("Northern Iowa", {"count": 1, "pct": 0.00, "result": "L"}),
            ]),
        },
        "Saturday": {
            "round": "R32",
            "date": "2026-03-21",
            "picks": OrderedDict([
                ("Arkansas", {"count": 393, "pct": 0.33, "result": "W"}),
                ("Illinois", {"count": 258, "pct": 0.22, "result": "W"}),
                ("Gonzaga", {"count": 144, "pct": 0.12, "result": "L"}),
                ("Michigan State", {"count": 144, "pct": 0.12, "result": "W"}),
                ("Houston", {"count": 63, "pct": 0.05, "result": "W"}),
                ("Vanderbilt", {"count": 59, "pct": 0.05, "result": "L"}),
                ("Duke", {"count": 50, "pct": 0.04, "result": "W"}),
                ("Nebraska", {"count": 26, "pct": 0.02, "result": "W"}),
                ("Michigan", {"count": 19, "pct": 0.02, "result": "W"}),
                ("Texas", {"count": 16, "pct": 0.01, "result": "W"}),
                ("NO PICK", {"count": 9, "pct": 0.01, "result": "L"}),
                ("Louisville", {"count": 4, "pct": 0.00, "result": "L"}),
                ("VCU", {"count": 2, "pct": 0.00, "result": "L"}),
                ("TCU", {"count": 1, "pct": 0.00, "result": "L"}),
                ("High Point", {"count": 1, "pct": 0.00, "result": "L"}),
            ]),
        },
        "Sunday": {
            "round": "R32",
            "date": "2026-03-22",
            "survivors_header": {"survivors": 764, "eliminated_total": 1051, "day4_losses": 205, "missing": 8},
            "picks": OrderedDict([
                ("Purdue", {"count": 191, "pct": 0.20, "result": "W"}),
                ("Connecticut", {"count": 177, "pct": 0.18, "result": "W"}),
                ("Iowa State", {"count": 136, "pct": 0.14, "result": "W"}),
                ("St. John's", {"count": 130, "pct": 0.13, "result": "W"}),
                ("Texas Tech", {"count": 59, "pct": 0.06, "result": "L"}),
                ("Virginia", {"count": 58, "pct": 0.06, "result": "L"}),
                ("Florida", {"count": 58, "pct": 0.06, "result": "L"}),
                ("Tennessee", {"count": 54, "pct": 0.06, "result": "W"}),
                ("Alabama", {"count": 40, "pct": 0.04, "result": "W"}),
                ("Arizona", {"count": 36, "pct": 0.04, "result": "W"}),
                ("Kansas", {"count": 13, "pct": 0.01, "result": "L"}),
                ("UCLA", {"count": 8, "pct": 0.01, "result": "L"}),
                ("NO PICK", {"count": 8, "pct": 0.01, "result": "L"}),
                ("Kentucky", {"count": 1, "pct": 0.00, "result": "L"}),
            ]),
        },
    },
}

# ─── Splash Contest (845 entries) ────────────────────────────────────────────
# After Thu: ~644 alive | After Fri: 607 alive | After Sat: 502 alive
SPLASH_CONTEST = {
    "name": "Splash Contest",
    "total_entries": 845,
    "survivor_snapshots": {"Thursday": None, "Friday": 607, "Saturday": 502, "Sunday": 412},
    "days": {
        "Thursday": {
            "round": "R64",
            "date": "2026-03-19",
            "picks": OrderedDict([
                ("Nebraska", {"count": 157, "pct": 0.186, "result": "W"}),
                ("Arkansas", {"count": 128, "pct": 0.151, "result": "W"}),
                ("Gonzaga", {"count": 121, "pct": 0.143, "result": "W"}),
                ("Wisconsin", {"count": 98, "pct": 0.116, "result": "L"}),
                ("Vanderbilt", {"count": 73, "pct": 0.086, "result": "W"}),
                ("Illinois", {"count": 57, "pct": 0.067, "result": "W"}),
                ("Michigan State", {"count": 53, "pct": 0.063, "result": "W"}),
                ("St. Mary's", {"count": 28, "pct": 0.033, "result": "L"}),
                ("Ohio State", {"count": 22, "pct": 0.026, "result": "L"}),
                ("Georgia", {"count": 19, "pct": 0.022, "result": "L"}),
                ("Louisville", {"count": 18, "pct": 0.021, "result": "W"}),
                ("BYU", {"count": 17, "pct": 0.020, "result": "L"}),
                ("North Carolina", {"count": 10, "pct": 0.012, "result": "L"}),
                ("Houston", {"count": 9, "pct": 0.011, "result": "W"}),
                ("St. Louis", {"count": 8, "pct": 0.009, "result": "W"}),
                ("VCU", {"count": 8, "pct": 0.009, "result": "W"}),
                ("South Florida", {"count": 5, "pct": 0.006, "result": "L"}),
                ("Duke", {"count": 5, "pct": 0.006, "result": "W"}),
                ("Texas", {"count": 3, "pct": 0.004, "result": "W"}),
                ("Michigan", {"count": 2, "pct": 0.002, "result": "W"}),
                ("Texas A&M", {"count": 1, "pct": 0.001, "result": "W"}),
                ("Troy", {"count": 1, "pct": 0.001, "result": "L"}),
                ("TCU", {"count": 1, "pct": 0.001, "result": "W"}),
                ("NO PICK", {"count": 1, "pct": 0.001, "result": "L"}),
            ]),
        },
        "Friday": {
            "round": "R64",
            "date": "2026-03-20",
            "survivors_header": {"survivors": 607, "eliminated": 37, "missed": 31},
            "picks": OrderedDict([
                ("Kansas", {"count": 148, "pct": 0.230, "result": "W"}),
                ("Virginia", {"count": 117, "pct": 0.182, "result": "W"}),
                ("Alabama", {"count": 73, "pct": 0.113, "result": "W"}),
                ("St. John's", {"count": 69, "pct": 0.107, "result": "W"}),
                ("Connecticut", {"count": 48, "pct": 0.075, "result": "W"}),
                ("Tennessee", {"count": 32, "pct": 0.050, "result": "W"}),
                ("UCLA", {"count": 31, "pct": 0.048, "result": "W"}),
                ("Texas Tech", {"count": 30, "pct": 0.047, "result": "W"}),
                ("Purdue", {"count": 19, "pct": 0.030, "result": "W"}),
                ("Kentucky", {"count": 12, "pct": 0.019, "result": "W"}),
                ("Iowa State", {"count": 10, "pct": 0.016, "result": "W"}),
                ("Iowa", {"count": 8, "pct": 0.012, "result": "W"}),
                ("Utah State", {"count": 5, "pct": 0.008, "result": "W"}),
                ("Villanova", {"count": 4, "pct": 0.006, "result": "L"}),
                ("Arizona", {"count": 2, "pct": 0.003, "result": "W"}),
                ("Miami", {"count": 2, "pct": 0.003, "result": "W"}),
                ("Missouri", {"count": 1, "pct": 0.002, "result": "L"}),
                ("Florida", {"count": 1, "pct": 0.002, "result": "W"}),
                ("Clemson", {"count": 1, "pct": 0.002, "result": "L"}),
                ("NO PICK", {"count": 31, "pct": 0.048, "result": "L"}),
            ]),
        },
        "Saturday": {
            "round": "R32",
            "date": "2026-03-21",
            "survivors_header": {"survivors": 502, "eliminated": 105, "missed": 17},
            "picks": OrderedDict([
                ("Arkansas", {"count": 216, "pct": 0.356, "result": "W"}),
                ("Illinois", {"count": 169, "pct": 0.278, "result": "W"}),
                ("Gonzaga", {"count": 66, "pct": 0.109, "result": "L"}),
                ("Michigan State", {"count": 51, "pct": 0.084, "result": "W"}),
                ("Houston", {"count": 34, "pct": 0.056, "result": "W"}),
                ("Vanderbilt", {"count": 20, "pct": 0.033, "result": "L"}),
                ("Duke", {"count": 16, "pct": 0.026, "result": "W"}),
                ("Michigan", {"count": 9, "pct": 0.015, "result": "W"}),
                ("Nebraska", {"count": 6, "pct": 0.010, "result": "W"}),
                ("Louisville", {"count": 1, "pct": 0.002, "result": "L"}),
                ("Texas", {"count": 1, "pct": 0.002, "result": "W"}),
                ("VCU", {"count": 1, "pct": 0.002, "result": "L"}),
                ("St. Louis", {"count": 0, "pct": 0.000, "result": "L"}),
                ("TCU", {"count": 0, "pct": 0.000, "result": "L"}),
                ("Texas A&M", {"count": 0, "pct": 0.000, "result": "L"}),
                ("High Point", {"count": 0, "pct": 0.000, "result": "L"}),
                ("NO PICK", {"count": 17, "pct": 0.028, "result": "L"}),
            ]),
        },
        "Sunday": {
            "round": "R32",
            "date": "2026-03-22",
            "picks": OrderedDict([
                ("Purdue", {"count": 112, "pct": 0.223, "result": "W"}),
                ("St. John's", {"count": 78, "pct": 0.155, "result": "W"}),
                ("Connecticut", {"count": 78, "pct": 0.155, "result": "W"}),
                ("Iowa State", {"count": 77, "pct": 0.153, "result": "W"}),
                ("Florida", {"count": 43, "pct": 0.086, "result": "L"}),
                ("Tennessee", {"count": 34, "pct": 0.068, "result": "W"}),
                ("Texas Tech", {"count": 23, "pct": 0.046, "result": "L"}),
                ("Alabama", {"count": 20, "pct": 0.040, "result": "W"}),
                ("Arizona", {"count": 13, "pct": 0.026, "result": "W"}),
                ("Virginia", {"count": 12, "pct": 0.024, "result": "L"}),
                ("UCLA", {"count": 3, "pct": 0.006, "result": "L"}),
                ("Kansas", {"count": 2, "pct": 0.004, "result": "L"}),
                ("Kentucky", {"count": 1, "pct": 0.002, "result": "L"}),
                ("Miami", {"count": 1, "pct": 0.002, "result": "L"}),
                ("NO PICK", {"count": 5, "pct": 0.010, "result": "L"}),
            ]),
        },
    },
}

CONTESTS = {
    "Sleeping Beauty": SLEEPING_BEAUTY,
    "Splash Contest": SPLASH_CONTEST,
}

# ─── My Entries ──────────────────────────────────────────────────────────────
MY_ENTRIES = {
    "Sleeping Beauty": {
        "Entry 1": {
            "alive": True,
            "picks": {
                "Thursday": {"team": "Nebraska", "result": "W"},
                "Friday": {"team": "Tennessee", "result": "W"},
                "Saturday": {"team": "Arkansas", "result": "W"},
                "Sunday": {"team": "Connecticut", "result": "W"},
            },
            "used_teams": ["Nebraska", "Tennessee", "Arkansas", "Connecticut"],
        },
        "Entry 2": {
            "alive": False,
            "eliminated_day": "Thursday",
            "eliminated_by": "St. Mary's lost to Texas A&M",
            "picks": {
                "Thursday": {"team": "St. Mary's", "result": "L"},
            },
            "used_teams": ["St. Mary's"],
        },
        "Entry 3": {
            "alive": False,
            "eliminated_day": "Thursday",
            "eliminated_by": "Wisconsin lost to High Point",
            "picks": {
                "Thursday": {"team": "Wisconsin", "result": "L"},
            },
            "used_teams": ["Wisconsin"],
        },
    },
    "Splash Contest": {
        "Entry 1": {
            "alive": False,
            "eliminated_day": "Thursday",
            "eliminated_by": "Wisconsin lost to High Point",
            "picks": {
                "Thursday": {"team": "Wisconsin", "result": "L"},
            },
            "used_teams": ["Wisconsin"],
        },
        "Entry 2": {
            "alive": True,
            "picks": {
                "Thursday": {"team": "Arkansas", "result": "W"},
                "Friday": {"team": "Kansas", "result": "W"},
                "Saturday": {"team": "Illinois", "result": "W"},
                "Sunday": {"team": "Connecticut", "result": "W"},
            },
            "used_teams": ["Arkansas", "Kansas", "Illinois", "Connecticut"],
        },
        "Entry 3": {
            "alive": True,
            "picks": {
                "Thursday": {"team": "Vanderbilt", "result": "W"},
                "Friday": {"team": "Connecticut", "result": "W"},
                "Saturday": {"team": "Arkansas", "result": "W"},
                "Sunday": {"team": "Iowa State", "result": "W"},
            },
            "used_teams": ["Vanderbilt", "Connecticut", "Arkansas", "Iowa State"],
        },
        "Entry 4": {
            "alive": False,
            "eliminated_day": "Sunday",
            "eliminated_by": "Texas Tech lost to Alabama",
            "picks": {
                "Thursday": {"team": "Nebraska", "result": "W"},
                "Friday": {"team": "Tennessee", "result": "W"},
                "Saturday": {"team": "Arkansas", "result": "W"},
                "Sunday": {"team": "Texas Tech", "result": "L"},
            },
            "used_teams": ["Nebraska", "Tennessee", "Arkansas", "Texas Tech"],
        },
        "Entry 5": {
            "alive": False,
            "eliminated_day": "Thursday",
            "eliminated_by": "St. Mary's lost to Texas A&M",
            "picks": {
                "Thursday": {"team": "St. Mary's", "result": "L"},
            },
            "used_teams": ["St. Mary's"],
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def compute_eliminations(contest_data):
    """Calculate cumulative entries eliminated each day."""
    elim_by_day = {}
    for day_name, day_data in contest_data["days"].items():
        killed = sum(
            p["count"] for p in day_data["picks"].values()
            if p.get("result") == "L"
        )
        elim_by_day[day_name] = killed
    return elim_by_day


def estimate_alive(contest_data):
    """Estimate remaining alive entries."""
    total = contest_data["total_entries"]
    if total is None:
        return None
    elim = compute_eliminations(contest_data)
    return total - sum(elim.values())


def get_available_next_round_teams(used_teams):
    """Get teams playing in the next round that haven't been used."""
    all_teams = []
    for g in NEXT_ROUND_GAMES:
        for i, team in enumerate(g["teams"]):
            if team not in used_teams:
                all_teams.append({
                    "team": team,
                    "seed": g["seeds"][i],
                    "game": g["game"],
                    "time": g["time"],
                    "day": g.get("day", ""),
                    "region": g.get("region", ""),
                })
    return all_teams


def seed_to_win_prob(seed, opp_seed):
    """Win probability based on seed matchup in R32.
    
    Uses historical R32 win rates calibrated to actual outcomes.
    A 1-seed vs 9-seed should be ~75%, not the 66% the old model gave.
    """
    # KenPom-style strength ratings tuned for R32 matchups
    # These yield: 1v9=75%, 2v7=65%, 3v6=60%, 4v5=56%
    seed_strength = {
        1: 1.00, 2: 0.85, 3: 0.75, 4: 0.65, 5: 0.55,
        6: 0.48, 7: 0.42, 8: 0.35, 9: 0.33, 10: 0.28,
        11: 0.22, 12: 0.18,
    }
    my_str = seed_strength.get(seed, 0.30)
    opp_str = seed_strength.get(opp_seed, 0.30)
    wp = my_str / (my_str + opp_str)
    return round(wp, 3)


def future_value_score(seed, rounds_remaining=4):
    """Score 0.0-1.0: how valuable is this team to save for later?
    
    Higher seeds are more valuable to preserve for later rounds
    when there are fewer safe picks available.
    """
    seed_base = max(0, (13 - seed) / 12)  # 1-seed = 1.0, 12-seed = 0.08
    round_factor = min(1.0, rounds_remaining / 4)
    return round(seed_base * round_factor, 3)


def safety_score(win_prob, opp_pct, fv, survival=1.0):
    """Safety pick score: maximize survival probability.
    
    Win probability is DOMINANT. FV is a gentle tiebreaker (max 15% discount).
    A 1-seed at 75% win prob should always outscore a 9-seed at 25%,
    regardless of future value.
    
    Old formula: wp * (1 - 0.7*fv) crushed 1-seeds to 0.3x multiplier.
    New formula: wp * (1 - 0.15*fv) gives 1-seeds a 0.85x multiplier.
    """
    return win_prob * (1 - 0.15 * fv) * (0.3 + 0.7 * survival)


def leverage_score(win_prob, opp_pct, fv, survival=1.0):
    """Leverage pick score: maximize edge over field.
    
    FV matters more here (30% max discount) because leverage is about
    long-run strategy. But win_prob still dominates — you can't gain
    leverage by picking a team that loses.
    """
    return ((1 - opp_pct) ** 0.6) * win_prob * (1 - 0.3 * fv) * (survival ** 0.5)


# ═══════════════════════════════════════════════════════════════════════════════
# UI RENDERING
# ═══════════════════════════════════════════════════════════════════════════════

def render_entry_card(entry_name, entry_data, contest_name):
    """Render a single entry card with pick history."""
    alive = entry_data.get("alive", False)
    badge = "alive-badge" if alive else "dead-badge"
    badge_text = "ALIVE" if alive else "ELIMINATED"
    
    st.markdown(f"""
    <div style="background:#111827; border-radius:12px; padding:16px; margin:8px 0; border:1px solid {'#065f46' if alive else '#7f1d1d'};">
        <div style="display:flex; align-items:center; margin-bottom:10px;">
            <span style="color:#e0e0e0; font-size:1.15em; font-weight:700;">{entry_name}</span>
            <span class="{badge}">{badge_text}</span>
        </div>
    """, unsafe_allow_html=True)
    
    if not alive:
        reason = entry_data.get("eliminated_by", "Unknown")
        st.markdown(f'<div style="color:#f87171; font-size:0.85em; margin-bottom:8px;">💀 {reason}</div>', unsafe_allow_html=True)
    
    for day, pick_info in entry_data.get("picks", {}).items():
        team = pick_info["team"]
        result = pick_info["result"]
        if result == "W":
            card_class = "win"
            icon = "✅"
        elif result == "L":
            card_class = "loss"
            icon = "❌"
        else:
            card_class = "pending"
            icon = "⏳"
        
        st.markdown(f"""
        <div class="pick-card {card_class}">
            {icon} <strong>{day}</strong>: {team} 
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)


def render_opponent_picks(day_name, day_data, total_entries):
    """Render opponent pick distribution for a day."""
    picks = day_data["picks"]
    if not picks:
        st.info(f"⏳ No data yet for {day_name}. Upload screenshots to add.")
        return
    
    total_picked = sum(p["count"] for p in picks.values())
    killed = sum(p["count"] for p in picks.values() if p.get("result") == "L")
    survived = sum(p["count"] for p in picks.values() if p.get("result") == "W")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Picks", f"{total_picked:,}")
    with col2:
        st.metric("Survived", f"{survived:,}", delta=None)
    with col3:
        st.metric("Eliminated", f"{killed:,}", delta=f"-{killed:,}" if killed > 0 else None, delta_color="inverse")
    
    st.markdown("---")
    
    # Table header
    st.markdown("""
    <div class="opp-row" style="border-bottom:2px solid #2a3050; font-weight:700; color:#9ca3af;">
        <span class="opp-team">Team</span>
        <span style="flex-grow:1; text-align:center;">Distribution</span>
        <span class="opp-pct">%</span>
        <span class="opp-count">Count</span>
        <span class="opp-result">Result</span>
    </div>
    """, unsafe_allow_html=True)
    
    for team, data in picks.items():
        pct = data["pct"]
        count = data["count"]
        result = data.get("result", "?")
        
        if result == "W":
            bar_class = "bar-fill-green"
            result_icon = "✅"
        elif result == "L":
            bar_class = "bar-fill-red"
            result_icon = "❌"
        else:
            bar_class = "bar-fill-yellow"
            result_icon = "⏳"
        
        bar_width = min(pct * 300, 100)  # scale
        
        st.markdown(f"""
        <div class="opp-row">
            <span class="opp-team">{team}</span>
            <div class="bar-bg">
                <div class="{bar_class}" style="width:{bar_width}%;"></div>
            </div>
            <span class="opp-pct">{pct:.0%}</span>
            <span class="opp-count">{count:,}</span>
            <span class="opp-result">{result_icon}</span>
        </div>
        """, unsafe_allow_html=True)


def render_next_round_recommendations(entry_name, entry_data, contest_data):
    """Show next-round pick recommendations for a live entry, with schedule awareness."""
    used = set(entry_data.get("used_teams", []))
    available = get_available_next_round_teams(list(used))
    
    if not available:
        st.warning(f"No available teams for {CURRENT_ROUND} for {entry_name}!")
        return
    
    # Count available teams for each game day AFTER this pick
    thu_teams_available = {t for t in BRACKET_SCHEDULE 
                          if BRACKET_SCHEDULE[t]["s16_day"] == "Thu" and t not in used}
    fri_teams_available = {t for t in BRACKET_SCHEDULE 
                          if BRACKET_SCHEDULE[t]["s16_day"] == "Fri" and t not in used}
    
    st.markdown(f"### 🎯 {CURRENT_ROUND} Recommendations — {entry_name}")
    st.caption(f"Used teams: {', '.join(sorted(used))}")
    
    # Show schedule depth
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**Thu S16 pool**: {len(thu_teams_available)} teams")
    with col_b:
        st.markdown(f"**Fri S16 pool**: {len(fri_teams_available)} teams")
    
    recs = []
    for t in available:
        team = t["team"]
        seed = t["seed"]
        game = t["game"]
        time = t["time"]
        game_day = t.get("day", "")
        
        # Find opponent seed
        opp_team = ""
        opp_seed = seed
        for g in NEXT_ROUND_GAMES:
            if team in g["teams"]:
                idx = g["teams"].index(team)
                opp_idx = 1 - idx
                opp_seed = g["seeds"][opp_idx]
                opp_team = g["teams"][opp_idx]
                break
        
        wp = seed_to_win_prob(seed, opp_seed)
        # 3 rounds remaining after S16: E8, F4, Championship
        fv = future_value_score(seed, rounds_remaining=3)
        
        # Schedule info
        sched = BRACKET_SCHEDULE.get(team, {})
        s16_day = sched.get("s16_day", "?")
        region = sched.get("region", "?")
        
        # How many teams remain in the OTHER day's pool after using this team?
        # (This team plays on s16_day; check if picking it thins tomorrow's options)
        if s16_day == "Thu":
            remaining_this_day = len(thu_teams_available - {team})
            remaining_other_day = len(fri_teams_available)
        else:
            remaining_this_day = len(fri_teams_available - {team})
            remaining_other_day = len(thu_teams_available)
        
        # Estimate opponent pick % from seed
        opp_pct = max(0.01, (13 - seed) / 80)
        
        s_score = safety_score(wp, opp_pct, fv)
        l_score = leverage_score(wp, opp_pct, fv)
        
        recs.append({
            "team": team,
            "seed": seed,
            "opponent": opp_team,
            "opp_seed": opp_seed,
            "game": game,
            "time": time,
            "game_day": game_day,
            "win_prob": wp,
            "fv": fv,
            "opp_pct": opp_pct,
            "safety": s_score,
            "leverage": l_score,
            "s16_day": s16_day,
            "region": region,
            "remaining_this_day": remaining_this_day,
            "remaining_other_day": remaining_other_day,
        })
    
    # Sort by safety score
    safety_sorted = sorted(recs, key=lambda x: x["safety"], reverse=True)
    leverage_sorted = sorted(recs, key=lambda x: x["leverage"], reverse=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🛡️ Safety Picks")
        st.caption("Maximize win probability, gentle FV tiebreaker")
        for i, r in enumerate(safety_sorted[:6]):
            tag = '🥇' if i == 0 else ('🥈' if i == 1 else '🥉' if i == 2 else '  ')
            pool_warn = ""
            if r["remaining_this_day"] <= 2:
                pool_warn = f" ⚠️ only {r['remaining_this_day']} {r['s16_day']} options left"
            st.markdown(f"""
            <div style="background:#0f2a1e; border-radius:8px; padding:10px 14px; margin:4px 0; border-left:3px solid #10b981;">
                <div style="color:#6ee7b7; font-weight:700;">{tag} ({r['seed']}) {r['team']}</div>
                <div style="color:#9ca3af; font-size:0.85em;">
                    vs ({r['opp_seed']}) {r['opponent']} · {r['time']}<br/>
                    Win: <strong style="color:#60a5fa;">{r['win_prob']:.0%}</strong> · 
                    FV: {r['fv']:.2f} · 
                    Field: ~{r['opp_pct']:.0%}<br/>
                    <span class="safety-tag">Safety: {r['safety']:.3f}</span>
                    <span style="background:#1e293b;color:#94a3b8;padding:2px 6px;border-radius:4px;font-size:0.75em;margin-left:4px;">{r['s16_day']} · {r['region']}</span>
                    <span style="color:#6b7280;font-size:0.75em;">{pool_warn}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### ⚡ Leverage Picks")
        st.caption("Maximize edge over opponent field")
        for i, r in enumerate(leverage_sorted[:6]):
            tag = '🥇' if i == 0 else ('🥈' if i == 1 else '🥉' if i == 2 else '  ')
            pool_warn = ""
            if r["remaining_this_day"] <= 2:
                pool_warn = f" ⚠️ only {r['remaining_this_day']} {r['s16_day']} options left"
            st.markdown(f"""
            <div style="background:#1e1b4b; border-radius:8px; padding:10px 14px; margin:4px 0; border-left:3px solid #6366f1;">
                <div style="color:#a5b4fc; font-weight:700;">{tag} ({r['seed']}) {r['team']}</div>
                <div style="color:#9ca3af; font-size:0.85em;">
                    vs ({r['opp_seed']}) {r['opponent']} · {r['time']}<br/>
                    Win: <strong style="color:#60a5fa;">{r['win_prob']:.0%}</strong> · 
                    FV: {r['fv']:.2f} · 
                    Field: ~{r['opp_pct']:.0%}<br/>
                    <span class="leverage-tag">Leverage: {r['leverage']:.3f}</span>
                    <span style="background:#1e293b;color:#94a3b8;padding:2px 6px;border-radius:4px;font-size:0.75em;margin-left:4px;">{r['s16_day']} · {r['region']}</span>
                    <span style="color:#6b7280;font-size:0.75em;">{pool_warn}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    st.caption(f"Field % uses seed-based estimates until {CURRENT_ROUND} screenshot data is available.")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.markdown("# 🏀 Survivor Pool Engine v5")
    st.markdown("*March Madness 2026 · Multi-Contest Tracker*")
    
    # ─── Sidebar ─────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## ⚙️ Controls")
        
        contest_choice = st.selectbox(
            "Active Contest",
            list(CONTESTS.keys()),
            index=0,
        )
        
        contest = CONTESTS[contest_choice]
        entries = MY_ENTRIES.get(contest_choice, {})
        
        st.markdown("---")
        
        # Contest stats
        if contest["total_entries"]:
            elim = compute_eliminations(contest)
            total_killed = sum(elim.values())
            
            # Use exact survivor count if available (from screenshot headers)
            snapshots = contest.get("survivor_snapshots", {})
            exact_alive = None
            for day in reversed(["Sunday", "Saturday", "Friday", "Thursday"]):
                if snapshots.get(day):
                    exact_alive = snapshots[day]
                    break
            
            alive_count = exact_alive if exact_alive else contest["total_entries"] - total_killed
            alive_entries_count = sum(1 for e in entries.values() if e.get("alive"))
            
            st.markdown(f"### 📊 {contest_choice}")
            st.metric("Total Entries", f"{contest['total_entries']:,}")
            st.metric("Alive (field)", f"{alive_count:,}" if exact_alive else f"~{alive_count:,}")
            st.metric("My Alive", f"{alive_entries_count} / {len(entries)}")
            st.metric("Kill Rate", f"{(contest['total_entries'] - alive_count)/contest['total_entries']:.1%}")
            
            st.markdown("---")
            st.markdown("##### Eliminations by Day")
            for day, count in elim.items():
                if count > 0:
                    st.markdown(f"**{day}**: {count:,} ({count/contest['total_entries']:.1%})")
        else:
            st.info(f"{contest_choice}: Awaiting data. Upload screenshots to populate.")
        
        st.markdown("---")
        st.markdown("##### 🔄 Data Status")
        for day_name, day_data in contest["days"].items():
            has_data = bool(day_data["picks"])
            icon = "✅" if has_data else "⏳"
            st.markdown(f"{icon} {day_name} {'(' + day_data['round'] + ')' if has_data else '— no data'}")
    
    # ─── Main Content ────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 My Entries",
        "📊 Opponent Picks",
        f"🎯 {CURRENT_ROUND}",
        "📅 Bracket",
    ])
    
    # ─── Tab 1: My Entries ───────────────────────────────────────────────
    with tab1:
        st.markdown(f"## My Entries — {contest_choice}")
        
        if not entries:
            st.info(f"No entries configured for {contest_choice} yet.")
        else:
            alive_count = sum(1 for e in entries.values() if e.get("alive"))
            dead_count = len(entries) - alive_count
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Entries", len(entries))
            with col2:
                st.metric("Alive", alive_count)
            with col3:
                st.metric("Eliminated", dead_count)
            
            st.markdown("---")
            
            for entry_name, entry_data in entries.items():
                render_entry_card(entry_name, entry_data, contest_choice)
                st.markdown("")
    
    # ─── Tab 2: Opponent Picks ───────────────────────────────────────────
    with tab2:
        st.markdown(f"## Opponent Pick Distributions — {contest_choice}")
        
        if contest["total_entries"] is None:
            st.info(f"No data loaded for {contest_choice}. Upload screenshots to populate.")
        else:
            day_choice = st.selectbox(
                "Select Day",
                list(contest["days"].keys()),
                index=2,  # Default to Saturday (most recent with data)
            )
            
            day_data = contest["days"][day_choice]
            st.markdown(f"### {day_choice} — {day_data['round']}")
            render_opponent_picks(day_choice, day_data, contest["total_entries"])
    
    # ─── Tab 3: Next Round Recommendations ─────────────────────────────────
    with tab3:
        st.markdown(f"## 🎯 {CURRENT_ROUND} Pick Strategy")
        st.markdown(f"*{CURRENT_ROUND_LABEL}*")
        
        if not entries:
            st.info(f"No entries configured for {contest_choice}.")
        else:
            alive_entries = {k: v for k, v in entries.items() if v.get("alive")}
            dead_entries = {k: v for k, v in entries.items() if not v.get("alive")}
            
            if not alive_entries:
                st.error(f"All entries eliminated in {contest_choice}.")
            else:
                for entry_name, entry_data in alive_entries.items():
                    render_next_round_recommendations(entry_name, entry_data, contest)
                    st.markdown("---")
            
            # Show eliminated entries
            if dead_entries:
                with st.expander(f"💀 Eliminated Entries ({len(dead_entries)})"):
                    for entry_name, entry_data in dead_entries.items():
                        reason = entry_data.get("eliminated_by", "Unknown")
                        st.markdown(f"**{entry_name}** — {reason}")
    
    # ─── Tab 4: Bracket ──────────────────────────────────────────────────
    with tab4:
        st.markdown(f"## 🏆 {CURRENT_ROUND} Bracket")
        st.markdown(f"*{CURRENT_ROUND_LABEL}*")
        
        for day_label, day_filter in [("Thursday March 26", "Thursday"), ("Friday March 27", "Friday")]:
            st.markdown(f"### {day_label}")
            day_games = [g for g in NEXT_ROUND_GAMES if g.get("day") == day_filter]
            
            for g in day_games:
                s1, s2 = g["seeds"]
                t1, t2 = g["teams"]
                region = g.get("region", "")
                
                # Check if either team is used by our entries
                used_by_entry = []
                if contest_choice in MY_ENTRIES:
                    for ename, edata in MY_ENTRIES[contest_choice].items():
                        if not edata.get("alive"):
                            continue
                        for team in [t1, t2]:
                            if team in edata.get("used_teams", []):
                                used_by_entry.append(f"{team} used by {ename}")
                
                highlight = " · ".join(used_by_entry) if used_by_entry else ""
                highlight_style = "border-left:3px solid #f59e0b;" if used_by_entry else "border-left:3px solid #2a3050;"
                
                st.markdown(f"""
                <div style="background:#111827; border-radius:8px; padding:12px 16px; margin:6px 0; {highlight_style}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="color:#e0e0e0; font-weight:700;">({s1}) {t1}</span>
                            <span style="color:#6b7280;"> vs </span>
                            <span style="color:#e0e0e0; font-weight:700;">({s2}) {t2}</span>
                        </div>
                        <span style="color:#9ca3af; font-size:0.9em;">{region} · {g['time']}</span>
                    </div>
                    {"<div style='color:#f59e0b; font-size:0.8em; margin-top:4px;'>⚠️ " + highlight + "</div>" if highlight else ""}
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### 🏆 Complete Sweet 16 Field")
        sweet16 = [
            ("South", [("(2) Houston", 2), ("(3) Illinois", 3), ("(4) Nebraska", 4), ("(9) Iowa", 9)]),
            ("West", [("(1) Arizona", 1), ("(4) Arkansas", 4), ("(2) Purdue", 2), ("(11) Texas", 11)]),
            ("East", [("(1) Duke", 1), ("(5) St. John's", 5), ("(3) Michigan St", 3), ("(2) UConn", 2)]),
            ("Midwest", [("(1) Michigan", 1), ("(4) Alabama", 4), ("(2) Iowa State", 2), ("(6) Tennessee", 6)]),
        ]
        for region_name, teams in sweet16:
            st.markdown(f"**{region_name}**")
            cols = st.columns(4)
            for i, (team_label, seed) in enumerate(teams):
                with cols[i]:
                    color = "#064e3b" if seed <= 3 else "#1e293b"
                    text_color = "#6ee7b7" if seed <= 3 else "#94a3b8"
                    st.markdown(f"""
                    <div style="background:{color}; border-radius:8px; padding:8px 12px; margin:3px 0; text-align:center;">
                        <span style="color:{text_color}; font-weight:600; font-size:0.9em;">{team_label}</span>
                    </div>
                    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
