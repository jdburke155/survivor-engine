import streamlit as st
import numpy as np
import pandas as pd
from scipy.stats import norm
import requests
import json
import os
import time
from datetime import datetime, date

st.set_page_config(page_title="MM Survivor Engine", layout="wide", page_icon="🏀")
SPREAD_SIGMA = 11.0
SAVE_FILE = "survivor_state.json"

# ═══════════════════════════════════════════════════════════
#  PERSISTENCE — Multi-contest aware
# ═══════════════════════════════════════════════════════════
# Per-contest keys (each contest has its own copy)
CONTEST_KEYS = ["contest_name", "total_entries", "my_entries", "pick_counts", "my_picks"]
# Shared keys (same across all contests)
SHARED_KEYS = ["n_sims", "current_day_idx", "spread_overrides", "manual_winners"]

DEFAULT_CONTESTS = {
    "contest_1": {"contest_name": "Contest 1", "total_entries": 900, "my_entries": 3, "pick_counts": {}, "my_picks": {}},
    "contest_2": {"contest_name": "Contest 2", "total_entries": 100, "my_entries": 1, "pick_counts": {}, "my_picks": {}},
}

def _ser(val):
    """Serialize sets/dicts for JSON."""
    if isinstance(val, set): return list(val)
    if isinstance(val, dict): return {str(k): (_ser(v) if isinstance(v, (set, dict)) else v) for k, v in val.items()}
    return val

def save_state():
    data = {"active_contest": st.session_state.get("active_contest", "contest_1"),
            "contests": {}, "shared": {}}
    for cid, cd in st.session_state.get("contests", {}).items():
        data["contests"][cid] = {k: _ser(cd.get(k)) for k in CONTEST_KEYS if k in cd}
    for k in SHARED_KEYS:
        v = st.session_state.get(k)
        if v is not None: data["shared"][k] = _ser(v)
    try:
        with open(SAVE_FILE, "w") as f: json.dump(data, f, indent=2)
        return True
    except: return False

def load_state():
    if not os.path.exists(SAVE_FILE): return None
    try:
        with open(SAVE_FILE, "r") as f: return json.load(f)
    except: return None

def export_state_json():
    data = {"active_contest": st.session_state.get("active_contest", "contest_1"),
            "contests": {}, "shared": {}}
    for cid, cd in st.session_state.get("contests", {}).items():
        data["contests"][cid] = {k: _ser(cd.get(k)) for k in CONTEST_KEYS if k in cd}
    for k in SHARED_KEYS:
        v = st.session_state.get(k)
        if v is not None: data["shared"][k] = _ser(v)
    return json.dumps(data, indent=2)

def import_state_json(json_str):
    try:
        data = json.loads(json_str)
        if "contests" in data:
            st.session_state.contests = data["contests"]
            st.session_state.active_contest = data.get("active_contest", "contest_1")
            for k in SHARED_KEYS:
                if k in data.get("shared", {}): st.session_state[k] = data["shared"][k]
        else:
            # Legacy single-contest import
            legacy = {k: data[k] for k in CONTEST_KEYS if k in data}
            if "contest_name" not in legacy: legacy["contest_name"] = "Imported"
            st.session_state.contests = {"contest_1": legacy}
            st.session_state.active_contest = "contest_1"
            for k in SHARED_KEYS:
                if k in data: st.session_state[k] = data[k]
        save_state()
        return True
    except: return False

def ctx():
    """Get active contest data dict."""
    cid = st.session_state.get("active_contest", "contest_1")
    cs = st.session_state.get("contests", {})
    if cid not in cs:
        cs[cid] = dict(DEFAULT_CONTESTS.get(cid, DEFAULT_CONTESTS["contest_1"]))
        st.session_state.contests = cs
    return cs[cid]

# ═══════════════════════════════════════════════════════════
#  BRACKET DATA
# ═══════════════════════════════════════════════════════════
FIRST_ROUND = {
    "R1_E_1v16":{"region":"East","seed_a":1,"team_a":"Duke","seed_b":16,"team_b":"Siena","spread":-27.5,"day":"Thu 3/19","time":"2:50 PM","loc":"Greenville, SC"},
    "R1_E_8v9":{"region":"East","seed_a":8,"team_a":"Ohio State","seed_b":9,"team_b":"TCU","spread":-2.5,"day":"Thu 3/19","time":"12:15 PM","loc":"Greenville, SC"},
    "R1_E_5v12":{"region":"East","seed_a":5,"team_a":"St. John's","seed_b":12,"team_b":"Northern Iowa","spread":-10.5,"day":"Fri 3/20","time":"7:10 PM","loc":"San Diego, CA"},
    "R1_E_4v13":{"region":"East","seed_a":4,"team_a":"Kansas","seed_b":13,"team_b":"Cal Baptist","spread":-13.5,"day":"Fri 3/20","time":"9:45 PM","loc":"San Diego, CA"},
    "R1_E_6v11":{"region":"East","seed_a":6,"team_a":"Louisville","seed_b":11,"team_b":"South Florida","spread":-6.5,"day":"Thu 3/19","time":"1:30 PM","loc":"Buffalo, NY"},
    "R1_E_3v14":{"region":"East","seed_a":3,"team_a":"Michigan State","seed_b":14,"team_b":"North Dakota State","spread":-16.5,"day":"Thu 3/19","time":"4:05 PM","loc":"Buffalo, NY"},
    "R1_E_7v10":{"region":"East","seed_a":7,"team_a":"UCLA","seed_b":10,"team_b":"UCF","spread":-6.5,"day":"Fri 3/20","time":"7:25 PM","loc":"Philadelphia, PA"},
    "R1_E_2v15":{"region":"East","seed_a":2,"team_a":"UConn","seed_b":15,"team_b":"Furman","spread":-19.5,"day":"Fri 3/20","time":"10:00 PM","loc":"Philadelphia, PA"},
    "R1_W_1v16":{"region":"West","seed_a":1,"team_a":"Arizona","seed_b":16,"team_b":"LIU","spread":-30.5,"day":"Fri 3/20","time":"1:35 PM","loc":"San Diego, CA"},
    "R1_W_8v9":{"region":"West","seed_a":8,"team_a":"Villanova","seed_b":9,"team_b":"Utah State","spread":2.5,"day":"Fri 3/20","time":"4:10 PM","loc":"San Diego, CA"},
    "R1_W_5v12":{"region":"West","seed_a":5,"team_a":"Wisconsin","seed_b":12,"team_b":"High Point","spread":-11.5,"day":"Thu 3/19","time":"1:50 PM","loc":"Portland, OR"},
    "R1_W_4v13":{"region":"West","seed_a":4,"team_a":"Arkansas","seed_b":13,"team_b":"Hawaii","spread":-15.5,"day":"Thu 3/19","time":"4:25 PM","loc":"Portland, OR"},
    "R1_W_6v11":{"region":"West","seed_a":6,"team_a":"BYU","seed_b":11,"team_b":"Texas/NC State","spread":-5.0,"day":"Thu 3/19","time":"7:25 PM","loc":"Portland, OR"},
    "R1_W_3v14":{"region":"West","seed_a":3,"team_a":"Gonzaga","seed_b":14,"team_b":"Kennesaw State","spread":-19.5,"day":"Thu 3/19","time":"10:00 PM","loc":"Portland, OR"},
    "R1_W_7v10":{"region":"West","seed_a":7,"team_a":"Miami FL","seed_b":10,"team_b":"Missouri","spread":-1.5,"day":"Fri 3/20","time":"10:10 PM","loc":"St. Louis, MO"},
    "R1_W_2v15":{"region":"West","seed_a":2,"team_a":"Purdue","seed_b":15,"team_b":"Queens","spread":-22.5,"day":"Fri 3/20","time":"7:35 PM","loc":"St. Louis, MO"},
    "R1_MW_1v16":{"region":"Midwest","seed_a":1,"team_a":"Michigan","seed_b":16,"team_b":"UMBC/Howard","spread":-28.0,"day":"Thu 3/19","time":"7:10 PM","loc":"Buffalo, NY"},
    "R1_MW_8v9":{"region":"Midwest","seed_a":8,"team_a":"Georgia","seed_b":9,"team_b":"Saint Louis","spread":-2.5,"day":"Thu 3/19","time":"9:45 PM","loc":"Buffalo, NY"},
    "R1_MW_5v12":{"region":"Midwest","seed_a":5,"team_a":"Texas Tech","seed_b":12,"team_b":"Akron","spread":-8.5,"day":"Fri 3/20","time":"12:40 PM","loc":"Tampa, FL"},
    "R1_MW_4v13":{"region":"Midwest","seed_a":4,"team_a":"Alabama","seed_b":13,"team_b":"Hofstra","spread":-12.5,"day":"Fri 3/20","time":"3:15 PM","loc":"Tampa, FL"},
    "R1_MW_6v11":{"region":"Midwest","seed_a":6,"team_a":"Tennessee","seed_b":11,"team_b":"SMU/Miami OH","spread":-6.0,"day":"Fri 3/20","time":"4:25 PM","loc":"Philadelphia, PA"},
    "R1_MW_3v14":{"region":"Midwest","seed_a":3,"team_a":"Virginia","seed_b":14,"team_b":"Wright State","spread":-17.5,"day":"Fri 3/20","time":"1:50 PM","loc":"Philadelphia, PA"},
    "R1_MW_7v10":{"region":"Midwest","seed_a":7,"team_a":"Kentucky","seed_b":10,"team_b":"Santa Clara","spread":-3.5,"day":"Fri 3/20","time":"12:15 PM","loc":"St. Louis, MO"},
    "R1_MW_2v15":{"region":"Midwest","seed_a":2,"team_a":"Iowa State","seed_b":15,"team_b":"Tennessee State","spread":-24.5,"day":"Fri 3/20","time":"2:50 PM","loc":"St. Louis, MO"},
    "R1_S_1v16":{"region":"South","seed_a":1,"team_a":"Florida","seed_b":16,"team_b":"Lehigh/PV A&M","spread":-28.0,"day":"Fri 3/20","time":"9:25 PM","loc":"Tampa, FL"},
    "R1_S_8v9":{"region":"South","seed_a":8,"team_a":"Clemson","seed_b":9,"team_b":"Iowa","spread":1.5,"day":"Fri 3/20","time":"6:50 PM","loc":"Tampa, FL"},
    "R1_S_5v12":{"region":"South","seed_a":5,"team_a":"Vanderbilt","seed_b":12,"team_b":"McNeese","spread":-11.5,"day":"Thu 3/19","time":"3:15 PM","loc":"Oklahoma City, OK"},
    "R1_S_4v13":{"region":"South","seed_a":4,"team_a":"Nebraska","seed_b":13,"team_b":"Troy","spread":-13.5,"day":"Thu 3/19","time":"12:40 PM","loc":"Oklahoma City, OK"},
    "R1_S_6v11":{"region":"South","seed_a":6,"team_a":"North Carolina","seed_b":11,"team_b":"VCU","spread":-2.5,"day":"Thu 3/19","time":"6:50 PM","loc":"Greenville, SC"},
    "R1_S_3v14":{"region":"South","seed_a":3,"team_a":"Illinois","seed_b":14,"team_b":"Penn","spread":-22.5,"day":"Thu 3/19","time":"9:25 PM","loc":"Greenville, SC"},
    "R1_S_7v10":{"region":"South","seed_a":7,"team_a":"Saint Mary's","seed_b":10,"team_b":"Texas A&M","spread":-2.5,"day":"Thu 3/19","time":"7:35 PM","loc":"Oklahoma City, OK"},
    "R1_S_2v15":{"region":"South","seed_a":2,"team_a":"Houston","seed_b":15,"team_b":"Idaho","spread":-21.5,"day":"Thu 3/19","time":"10:10 PM","loc":"Oklahoma City, OK"},
}

BRACKET_TREE = {
    "R2_E_top":("R1_E_1v16","R1_E_8v9"),"R2_E_upmid":("R1_E_5v12","R1_E_4v13"),
    "R2_E_lomid":("R1_E_6v11","R1_E_3v14"),"R2_E_bot":("R1_E_7v10","R1_E_2v15"),
    "R2_W_top":("R1_W_1v16","R1_W_8v9"),"R2_W_upmid":("R1_W_5v12","R1_W_4v13"),
    "R2_W_lomid":("R1_W_6v11","R1_W_3v14"),"R2_W_bot":("R1_W_7v10","R1_W_2v15"),
    "R2_MW_top":("R1_MW_1v16","R1_MW_8v9"),"R2_MW_upmid":("R1_MW_5v12","R1_MW_4v13"),
    "R2_MW_lomid":("R1_MW_6v11","R1_MW_3v14"),"R2_MW_bot":("R1_MW_7v10","R1_MW_2v15"),
    "R2_S_top":("R1_S_1v16","R1_S_8v9"),"R2_S_upmid":("R1_S_5v12","R1_S_4v13"),
    "R2_S_lomid":("R1_S_6v11","R1_S_3v14"),"R2_S_bot":("R1_S_7v10","R1_S_2v15"),
    "S16_E_top":("R2_E_top","R2_E_upmid"),"S16_E_bot":("R2_E_lomid","R2_E_bot"),
    "S16_W_top":("R2_W_top","R2_W_upmid"),"S16_W_bot":("R2_W_lomid","R2_W_bot"),
    "S16_MW_top":("R2_MW_top","R2_MW_upmid"),"S16_MW_bot":("R2_MW_lomid","R2_MW_bot"),
    "S16_S_top":("R2_S_top","R2_S_upmid"),"S16_S_bot":("R2_S_lomid","R2_S_bot"),
    "E8_E":("S16_E_top","S16_E_bot"),"E8_W":("S16_W_top","S16_W_bot"),
    "E8_MW":("S16_MW_top","S16_MW_bot"),"E8_S":("S16_S_top","S16_S_bot"),
    "FF_1":("E8_E","E8_W"),"FF_2":("E8_S","E8_MW"),
    "CHAMP":("FF_1","FF_2"),
}

TOURNAMENT_DAYS = ["Thu 3/19","Fri 3/20","Sat 3/21","Sun 3/22","Thu 3/26","Fri 3/27",
                   "Sat 3/28","Sun 3/29","Sat 4/4","Mon 4/6"]
ROUND_NAMES = {"Thu 3/19":"Rd of 64 (Thu)","Fri 3/20":"Rd of 64 (Fri)",
    "Sat 3/21":"Rd of 32 (Sat)","Sun 3/22":"Rd of 32 (Sun)",
    "Thu 3/26":"Sweet 16 (Thu)","Fri 3/27":"Sweet 16 (Fri)",
    "Sat 3/28":"Elite 8 (Sat)","Sun 3/29":"Elite 8 (Sun)",
    "Sat 4/4":"Final Four","Mon 4/6":"Championship"}
DAY_TO_DATE = {"Thu 3/19":"20260319","Fri 3/20":"20260320","Sat 3/21":"20260321",
    "Sun 3/22":"20260322","Thu 3/26":"20260326","Fri 3/27":"20260327",
    "Sat 3/28":"20260328","Sun 3/29":"20260329","Sat 4/4":"20260404","Mon 4/6":"20260406"}
REGION_DAY_R2 = {"East":"Sat 3/21","West":"Sun 3/22","Midwest":"Sun 3/22","South":"Sat 3/21"}
# S16/E8 mapping from 2026 regional sites: Houston+San Jose (Thu/Sat) = South+West, Chicago+DC (Fri/Sun) = East+Midwest
# Source: PoolGenius schedule grid — "East (Sunday) vs South (Saturday), West (Saturday) vs Midwest (Sunday)"
REGION_DAY_S16 = {"East":"Fri 3/27","West":"Thu 3/26","Midwest":"Fri 3/27","South":"Thu 3/26"}
REGION_DAY_E8 = {"East":"Sun 3/29","West":"Sat 3/28","Midwest":"Sun 3/29","South":"Sat 3/28"}

# ═══════════════════════════════════════════════════════════
#  SCHEDULE PAIRING LOGIC — which picks complement each other
# ═══════════════════════════════════════════════════════════
# Final Four pairings: East vs South (Sat 4/4), West vs Midwest (Sat 4/4)
FF_PAIRINGS = [("East", "South"), ("West", "Midwest")]

# For a championship pick to be possible, your E8 picks must come from regions
# that DON'T play each other in the FF. Valid E8 combos for championship viability:
# East + West, East + Midwest, South + West, South + Midwest
# INVALID: East + South (same FF semi), West + Midwest (same FF semi)
VALID_E8_COMBOS = [("East","West"),("East","Midwest"),("South","West"),("South","Midwest")]
INVALID_E8_COMBOS = [("East","South"),("West","Midwest")]

def get_team_schedule(team):
    """Get the day a team plays in each round (based on R64 day and region)."""
    region = get_team_region(team)
    r64_day = None
    for g in FIRST_ROUND.values():
        if g["team_a"] == team or g["team_b"] == team:
            r64_day = g["day"]; break
    if not region or not r64_day: return {}
    # R32 day follows R64 day: Thu→Sat, Fri→Sun
    r32_day = "Sat 3/21" if r64_day == "Thu 3/19" else "Sun 3/22"
    return {
        "R64": r64_day, "R32": r32_day,
        "S16": REGION_DAY_S16.get(region),
        "E8": REGION_DAY_E8.get(region),
        "FF": "Sat 4/4", "CHAMP": "Mon 4/6",
    }

def compute_day_conflicts(team, used_teams):
    """
    Check if picking this team creates day conflicts in future rounds.
    Returns dict with warnings for any round where used picks pile up on the same day.
    """
    team_sched = get_team_schedule(team)
    if not team_sched: return {}

    # Build schedule of already-used teams
    used_by_day = {}  # round -> day -> count of used teams on that day
    for ut in used_teams:
        ut_sched = get_team_schedule(ut)
        for rnd, day in ut_sched.items():
            if day:
                key = f"{rnd}|{day}"
                used_by_day[key] = used_by_day.get(key, 0) + 1

    conflicts = {}
    for rnd, day in team_sched.items():
        if not day: continue
        key = f"{rnd}|{day}"
        existing = used_by_day.get(key, 0)
        if existing >= 1 and rnd in ["E8", "FF"]:
            conflicts[rnd] = f"Already have {existing} pick(s) on {day} for {rnd}"
    return conflicts

def check_championship_feasibility(used_teams):
    """
    Check if current picks still allow a championship game pick.
    Returns (feasible: bool, warning: str or None).
    """
    e8_regions_used = set()
    for t in used_teams:
        region = get_team_region(t)
        sched = get_team_schedule(t)
        # If this team was used on an E8 day, it counts
        # But really we need to check: would this team be an E8 pick?
        # Simpler: track all regions of used teams
        if region:
            e8_regions_used.add(region)

    # Check if any invalid E8 combo is fully covered
    for r1, r2 in INVALID_E8_COMBOS:
        if r1 in e8_regions_used and r2 in e8_regions_used:
            return False, f"⚠️ Used teams from both {r1} and {r2} — these meet in the FF. No championship pick possible if both are E8 picks."

    return True, None

# ═══════════════════════════════════════════════════════════
#  ESPN API
# ═══════════════════════════════════════════════════════════
NAME_ALIASES = {
    "Duke Blue Devils":"Duke","Siena Saints":"Siena","Ohio State Buckeyes":"Ohio State",
    "TCU Horned Frogs":"TCU","St. John's Red Storm":"St. John's","St. John's (NY) Red Storm":"St. John's",
    "Northern Iowa Panthers":"Northern Iowa","Kansas Jayhawks":"Kansas",
    "California Baptist Lancers":"Cal Baptist","Louisville Cardinals":"Louisville",
    "South Florida Bulls":"South Florida","Michigan State Spartans":"Michigan State",
    "North Dakota State Bison":"North Dakota State","UCLA Bruins":"UCLA","UCF Knights":"UCF",
    "UConn Huskies":"UConn","Connecticut Huskies":"UConn","Furman Paladins":"Furman",
    "Arizona Wildcats":"Arizona","Long Island University Sharks":"LIU","LIU Sharks":"LIU",
    "Villanova Wildcats":"Villanova","Utah State Aggies":"Utah State","Wisconsin Badgers":"Wisconsin",
    "High Point Panthers":"High Point","Arkansas Razorbacks":"Arkansas",
    "Hawai'i Rainbow Warriors":"Hawaii","Hawaii Rainbow Warriors":"Hawaii",
    "BYU Cougars":"BYU","Texas Longhorns":"Texas","NC State Wolfpack":"NC State",
    "Gonzaga Bulldogs":"Gonzaga","Kennesaw State Owls":"Kennesaw State",
    "Miami Hurricanes":"Miami FL","Missouri Tigers":"Missouri","Purdue Boilermakers":"Purdue",
    "Queens University Royals":"Queens","Queens Royals":"Queens","Michigan Wolverines":"Michigan",
    "UMBC Retrievers":"UMBC","Howard Bison":"Howard","Georgia Bulldogs":"Georgia",
    "Saint Louis Billikens":"Saint Louis","Texas Tech Red Raiders":"Texas Tech","Akron Zips":"Akron",
    "Alabama Crimson Tide":"Alabama","Hofstra Pride":"Hofstra","Tennessee Volunteers":"Tennessee",
    "SMU Mustangs":"SMU","Miami (OH) RedHawks":"Miami OH","Miami Ohio RedHawks":"Miami OH",
    "Virginia Cavaliers":"Virginia","Wright State Raiders":"Wright State","Kentucky Wildcats":"Kentucky",
    "Santa Clara Broncos":"Santa Clara","Iowa State Cyclones":"Iowa State",
    "Tennessee State Tigers":"Tennessee State","Florida Gators":"Florida",
    "Lehigh Mountain Hawks":"Lehigh","Prairie View A&M Panthers":"Prairie View A&M",
    "Clemson Tigers":"Clemson","Iowa Hawkeyes":"Iowa","Vanderbilt Commodores":"Vanderbilt",
    "McNeese Cowboys":"McNeese","McNeese State Cowboys":"McNeese","Nebraska Cornhuskers":"Nebraska",
    "Troy Trojans":"Troy","North Carolina Tar Heels":"North Carolina","VCU Rams":"VCU",
    "Illinois Fighting Illini":"Illinois","Pennsylvania Quakers":"Penn","Penn Quakers":"Penn",
    "Saint Mary's Gaels":"Saint Mary's","Texas A&M Aggies":"Texas A&M","Houston Cougars":"Houston",
    "Idaho Vandals":"Idaho",
}
def normalize_name(n):
    if n in NAME_ALIASES: return NAME_ALIASES[n]
    for a, c in NAME_ALIASES.items():
        if c.lower() in n.lower(): return c
    return n

@st.cache_data(ttl=120)
def fetch_espn(date_str):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates={date_str}&groups=100&limit=100"
    try:
        resp = requests.get(url, timeout=10); resp.raise_for_status(); data = resp.json()
        results = []
        for ev in data.get("events", []):
            comp = ev.get("competitions", [{}])[0]
            st_info = ev.get("status", {}).get("type", {})
            is_final = st_info.get("completed", False)
            is_live = st_info.get("state", "") == "in"
            tms = comp.get("competitors", [])
            if len(tms) == 2:
                ra = normalize_name(tms[0].get("team",{}).get("displayName",""))
                rb = normalize_name(tms[1].get("team",{}).get("displayName",""))
                sa = int(tms[0].get("score",0) or 0); sb = int(tms[1].get("score",0) or 0)
                winner = loser = None
                if is_final:
                    if tms[0].get("winner"): winner, loser = ra, rb
                    elif tms[1].get("winner"): winner, loser = rb, ra
                    elif sa > sb: winner, loser = ra, rb
                    elif sb > sa: winner, loser = rb, ra
                results.append({"team_a":ra,"team_b":rb,"score_a":sa,"score_b":sb,
                    "winner":winner,"loser":loser,"is_final":is_final,"is_live":is_live,
                    "detail":st_info.get("detail","")})
        return results
    except: return []

def fetch_all():
    today = date.today(); out = {}
    for dl, ds in DAY_TO_DATE.items():
        if datetime.strptime(ds, "%Y%m%d").date() <= today:
            s = fetch_espn(ds)
            if s: out[dl] = s
    return out

def match_results(espn, bracket):
    winners = {}; losers = {}
    for gid, g in bracket.items():
        ta, tb = g["team_a"], g["team_b"]
        tap = [x.strip() for x in ta.split("/")]; tbp = [x.strip() for x in tb.split("/")]
        for dr in espn.values():
            for r in dr:
                if not r["is_final"] or not r["winner"]: continue
                ra, rb = r["team_a"], r["team_b"]
                if ((ra in tap or ra==ta) and (rb in tbp or rb==tb)) or \
                   ((rb in tap or rb==ta) and (ra in tbp or ra==tb)) or \
                   ((ra in tbp or ra==tb) and (rb in tap or rb==ta)) or \
                   ((rb in tbp or rb==tb) and (ra in tap or ra==ta)):
                    winners[gid]=r["winner"]; losers[gid]=r["loser"]; break
    return winners, losers

# ═══════════════════════════════════════════════════════════
#  BRACKET BUILD
# ═══════════════════════════════════════════════════════════
def get_region(gid):
    if "_E_" in gid or gid.endswith("_E"): return "East"
    if "_W_" in gid or gid.endswith("_W"): return "West"
    if "_MW_" in gid or gid.endswith("_MW"): return "Midwest"
    if "_S_" in gid or gid.endswith("_S"): return "South"
    return "TBD"
def get_round(gid):
    for p in ["CHAMP","S16","R2","R1","E8","FF"]:
        if gid.startswith(p): return p
    return "R1"
def assign_day(gid, region):
    r = get_round(gid)
    if r=="R2": return REGION_DAY_R2.get(region,"Sat 3/21")
    if r=="S16": return REGION_DAY_S16.get(region,"Thu 3/27")
    if r=="E8": return REGION_DAY_E8.get(region,"Sat 3/29")
    if r=="FF": return "Sat 4/4"
    if r=="CHAMP": return "Mon 4/6"
    return None
def build_bracket(winners):
    games = dict(FIRST_ROUND)
    tinfo = {}
    for g in FIRST_ROUND.values():
        tinfo[g["team_a"]]={"seed":g["seed_a"],"region":g["region"]}
        tinfo[g["team_b"]]={"seed":g["seed_b"],"region":g["region"]}
    for gid,(fa,fb) in BRACKET_TREE.items():
        ta=winners.get(fa); tb=winners.get(fb)
        region=get_region(gid)
        if region=="TBD":
            if gid=="FF_1": region="East/West"
            elif gid=="FF_2": region="South/Midwest"
            else: region="Championship"
        day=assign_day(gid, region.split("/")[0] if "/" in region else region)
        sa=tinfo[ta]["seed"] if ta and ta in tinfo else None
        sb=tinfo[tb]["seed"] if tb and tb in tinfo else None
        spread=None
        if sa and sb: spread=-round((sb-sa)*1.8,1)
        games[gid]={"region":region,"seed_a":sa,"team_a":ta or f"W({fa})",
            "seed_b":sb,"team_b":tb or f"W({fb})","spread":spread,"day":day,
            "time":"TBD","loc":"TBD","feeder_a":fa,"feeder_b":fb,
            "teams_known":ta is not None and tb is not None}
    return games

# ═══════════════════════════════════════════════════════════
#  PICK TRACKING & OPPONENT MODEL
# ═══════════════════════════════════════════════════════════
def get_all_teams():
    teams = set()
    for g in FIRST_ROUND.values():
        for t in [g["team_a"], g["team_b"]]:
            if "/" not in t: teams.add(t)
    return sorted(teams)

def get_team_seed(team):
    for g in FIRST_ROUND.values():
        if g["team_a"] == team: return g["seed_a"]
        if g["team_b"] == team: return g["seed_b"]
    return None

def get_team_region(team):
    """Look up region for a team."""
    for g in FIRST_ROUND.values():
        if g["team_a"] == team: return g["region"]
        if g["team_b"] == team: return g["region"]
    return None

def compute_region_penalty(team_region, used_teams, rd_idx, total_rds):
    """
    Penalize picking from a region you've already burned teams in.

    Logic: Each region provides ~5 game-days of teams (R64 Thu, R64 Fri, R32, S16, E8).
    Using 2+ teams from the same region before the Elite 8 is wasteful because:
      1. Those teams might face each other (you burned two when only one can advance)
      2. You'll have fewer options in that region's later-round games
      3. Only 1 team per region reaches the Final Four — save your picks

    Returns 0.0-1.0 multiplier (lower = bigger penalty).
    """
    if not team_region or not used_teams:
        return 1.0

    # Count how many teams from this region we've already used
    region_used = 0
    for t in used_teams:
        if get_team_region(t) == team_region:
            region_used += 1

    rounds_remaining = total_rds - rd_idx - 1
    if rounds_remaining <= 2:
        # Late tournament (E8/FF/Championship): regions are collapsing, less penalty
        if region_used >= 3: return 0.70
        if region_used >= 2: return 0.85
        return 1.0

    # Early/mid tournament: heavy penalty for region hoarding
    if region_used >= 3:
        return 0.40  # Already burned 3 from this region — very bad
    elif region_used >= 2:
        return 0.60  # Burned 2 — problematic
    elif region_used >= 1:
        return 0.85  # Burned 1 — slight preference to diversify
    return 1.0

def compute_scarcity_factor(team, used_teams, future_days, eliminated):
    """
    How many viable teams will you have left in future rounds if you pick this team today?

    Returns 0.0-1.0. Lower = picking this team leaves you dangerously thin later.

    If any future day would have ≤1 available team after this pick, that's a red flag.
    If you'd have 0 on any day, that's a death sentence (guaranteed elimination).
    """
    sim_used = set(used_teams) | {team}
    min_options = 999

    for ft in future_days:
        if not ft:
            continue
        available = [t for t in ft if t["team"] not in sim_used and t["team"] not in eliminated]
        min_options = min(min_options, len(available))

    if min_options == 999:
        return 1.0  # No future data yet
    if min_options == 0:
        return 0.1  # Would leave a future day with ZERO options — near death
    if min_options == 1:
        return 0.4  # Only 1 option on some future day — very risky
    if min_options == 2:
        return 0.7  # Tight but workable
    if min_options <= 4:
        return 0.9  # Fine
    return 1.0  # Plenty of options

def compute_entries_with_team_available(team, day_idx, pick_counts, total_entries):
    used = 0
    for d_i in range(day_idx):
        used += pick_counts.get(f"{TOURNAMENT_DAYS[d_i]}|{team}", 0)
    return max(total_entries - used, 0)

def compute_opp_pct_model(avail, rd_idx, total_rds, pick_counts, current_day, total_entries):
    if not avail: return {}
    has_actual = any(pick_counts.get(f"{current_day}|{t['team']}", 0) > 0 for t in avail)
    if has_actual:
        result = {}
        total_picks = sum(pick_counts.get(f"{current_day}|{t['team']}", 0) for t in avail)
        for t in avail:
            cnt = pick_counts.get(f"{current_day}|{t['team']}", 0)
            result[t["team"]] = cnt / max(total_picks, 1)
        return result
    BRAND = {"Duke","Kansas","UConn","Michigan","Florida","Arizona","Kentucky","North Carolina",
             "Gonzaga","Houston","Purdue","Michigan State","Alabama","Iowa State","Illinois",
             "Arkansas","Virginia","UCLA","Louisville","St. John's","Tennessee","Vanderbilt",
             "Nebraska","Texas Tech","BYU","Clemson","Iowa"}
    scores = {}; rr = total_rds - rd_idx
    for t in avail:
        wp = t["win_prob"]; seed = t.get("seed") or 8
        wp_floor = 0.45 if rr > 2 else 0.35
        if wp < wp_floor: scores[t["team"]] = 0.0; continue
        base = wp ** 4
        # Seed-saving: 1/2 heavily saved, 3 moderately saved
        if rr > 5: disc = {1:0.08,2:0.15,3:0.40}.get(seed, 1.0)
        elif rr > 3: disc = {1:0.25,2:0.45,3:0.65}.get(seed, 1.0)
        elif rr > 1: disc = {1:0.60,2:0.80}.get(seed, 1.0)
        else: disc = 1.0
        # R1 chalk boost: 4/5/6 seeds are the "obvious" survivor picks.
        # Tough R2 matchups make people want to burn them now.
        if rr > 5: chalk = {4:1.8, 5:1.8, 6:2.5}.get(seed, 1.0)
        elif rr > 3: chalk = {4:1.3, 5:1.3, 6:1.5}.get(seed, 1.0)
        else: chalk = 1.0
        brand = 1.15 if t["team"] in BRAND else 1.0
        scores[t["team"]] = base * disc * chalk * brand
    tot = sum(scores.values())
    if tot == 0: return {t["team"]: 1.0/len(avail) for t in avail}
    return {t: s/tot for t, s in scores.items()}

# ═══════════════════════════════════════════════════════════
#  SIMULATION ENGINE
# ═══════════════════════════════════════════════════════════
def win_prob(spread):
    if spread is None: return 0.5
    return float(norm.cdf(-spread / SPREAD_SIGMA))

def compute_future_value(seed, wp, rd_idx, total_rds):
    if seed is None: seed = 8
    rr = total_rds - rd_idx - 1
    if rr <= 0: return 0.0
    if seed == 1: premium = 0.95
    elif seed == 2: premium = 0.82
    elif seed == 3: premium = 0.60
    elif seed == 4: premium = 0.40
    elif seed == 5: premium = 0.25
    elif seed <= 7: premium = 0.10
    else: premium = 0.0
    return premium * min(rr/4.0, 1.0) * min(wp*1.3, 1.0)

def smart_future_pick(available, rounds_remaining, used_regions=None):
    """Pick best team for a future sim round with seed-saving AND region diversity."""
    if not available: return None
    if rounds_remaining <= 1: return max(available, key=lambda x: x["win_prob"])

    def region_ok(t):
        """Prefer teams from regions we haven't over-used."""
        if not used_regions: return True
        r = t.get("region")
        return used_regions.get(r, 0) < 2  # Allow up to 1 from same region

    if rounds_remaining > 3:
        # Early: avoid 1/2 seeds, prefer underused regions
        candidates = [t for t in available if (t.get("seed") or 99) > 2 and region_ok(t)]
        if not candidates:
            candidates = [t for t in available if (t.get("seed") or 99) > 2]
        if candidates: return max(candidates, key=lambda x: x["win_prob"])

    if rounds_remaining > 1:
        candidates = [t for t in available if (t.get("seed") or 99) > 1 and region_ok(t)]
        if not candidates:
            candidates = [t for t in available if (t.get("seed") or 99) > 1]
        if candidates: return max(candidates, key=lambda x: x["win_prob"])

    return max(available, key=lambda x: x["win_prob"])

def sim_survivor(pick, avail_today, future_days, n, rd_idx, total_rds, used, pick_counts, total_entries):
    today_map = {t["team"]: t["win_prob"] for t in avail_today}
    if pick not in today_map: return 0.0

    # Build region lookup from avail_today + future_days
    team_regions = {}
    for t in avail_today:
        team_regions[t["team"]] = t.get("region") or get_team_region(t["team"])
    for ft in future_days:
        for t in ft:
            team_regions[t["team"]] = t.get("region") or get_team_region(t["team"])

    known_future = [ft for ft in future_days if ft]
    survivals = 0

    for _ in range(n):
        ok = True; su = set(used); su.add(pick)

        # Track region usage for this sim path
        used_regions = {}
        for t in su:
            r = team_regions.get(t) or get_team_region(t)
            if r: used_regions[r] = used_regions.get(r, 0) + 1

        if np.random.random() >= today_map[pick]: ok = False
        elif known_future:
            for fi, ft in enumerate(known_future):
                rr = total_rds - (rd_idx + 1 + fi)
                av = [t for t in ft if t["team"] not in su]
                if not av: ok = False; break
                best = smart_future_pick(av, rr, used_regions)
                if best is None: ok = False; break
                su.add(best["team"])
                br = team_regions.get(best["team"])
                if br: used_regions[br] = used_regions.get(br, 0) + 1
                if np.random.random() >= best["win_prob"]: ok = False; break
        if ok: survivals += 1
    return survivals / max(n, 1)

def compute_safety_score(wp, fv, survival, region_pen=1.0, scarcity=1.0):
    """
    Safety = survive today, preserve future assets, diversify regions, maintain options.

    win_prob × (1 - 0.7×FV) × surv_factor × region_penalty × scarcity

    Region penalty: picking from an already-used region is penalized.
    Scarcity: if this pick would leave you with few future options, penalize.
    """
    surv_factor = (0.3 + 0.7 * survival) if survival > 0 else 0.5
    return wp * (1.0 - 0.7 * fv) * surv_factor * region_pen * scarcity

def compute_leverage_score(wp, opp_pct, fv, survival, region_pen=1.0, scarcity=1.0):
    """
    Leverage = contrarian close-game pick, don't waste regions or leave yourself thin.
    """
    contrarian = (1.0 - opp_pct) ** 1.5
    wp_capped = min(wp, 0.85) ** 0.5
    fv_penalty = 1.0 - 0.7 * fv
    surv_factor = survival ** 0.5 if survival > 0 else 0.5
    return contrarian * wp_capped * fv_penalty * surv_factor * region_pen * scarcity

MIN_WP_SAFETY = 0.55
MIN_WP_LEVERAGE = 0.50

# ═══════════════════════════════════════════════════════════
#  SESSION STATE INIT
# ═══════════════════════════════════════════════════════════
if "state_loaded" not in st.session_state:
    saved = load_state()
    if saved:
        if "contests" in saved:
            st.session_state.contests = saved["contests"]
            st.session_state.active_contest = saved.get("active_contest", "contest_1")
            for k in SHARED_KEYS:
                if k in saved.get("shared", {}): st.session_state[k] = saved["shared"][k]
        else:
            # Legacy migration
            legacy = {k: saved[k] for k in CONTEST_KEYS if k in saved}
            if "contest_name" not in legacy: legacy["contest_name"] = "Contest 1"
            st.session_state.contests = {"contest_1": legacy}
            st.session_state.active_contest = "contest_1"
            for k in SHARED_KEYS:
                if k in saved: st.session_state[k] = saved[k]
    st.session_state.state_loaded = True

# Apply defaults
if "contests" not in st.session_state:
    st.session_state.contests = {k: dict(v) for k, v in DEFAULT_CONTESTS.items()}
if "active_contest" not in st.session_state:
    st.session_state.active_contest = "contest_1"
for k, v in [("n_sims", 1000), ("current_day_idx", 0), ("spread_overrides", {}),
             ("manual_winners", {}), ("sim_results", None)]:
    if k not in st.session_state: st.session_state[k] = v
if "used_teams" not in st.session_state:
    st.session_state.used_teams = {}

# Active contest shortcut
C = ctx()

# ═══════════════════════════════════════════════════════════
#  FETCH & BUILD LIVE BRACKET
# ═══════════════════════════════════════════════════════════
with st.spinner("📡 Fetching ESPN results..."):
    espn_results = fetch_all()
    api_winners, api_losers = match_results(espn_results, FIRST_ROUND)
all_winners = {**api_winners, **st.session_state.manual_winners}
live_bracket = build_bracket(all_winners)
later = {gid:g for gid,g in live_bracket.items() if g.get("teams_known") and gid not in FIRST_ROUND}
if later:
    lw, ll = match_results(espn_results, later)
    all_winners.update(lw); api_losers.update(ll)
    live_bracket = build_bracket(all_winners)
eliminated = set(api_losers.values())
for gid in BRACKET_TREE:
    if gid in all_winners:
        g = live_bracket.get(gid)
        if g and g.get("teams_known"):
            w = all_winners[gid]
            if g["team_a"]!=w and "W(" not in g["team_a"]: eliminated.add(g["team_a"])
            if g["team_b"]!=w and "W(" not in g["team_b"]: eliminated.add(g["team_b"])
ALL_TEAMS = get_all_teams()
current_day = TOURNAMENT_DAYS[st.session_state.current_day_idx]

def get_live_info(ta, tb):
    for dr in espn_results.values():
        for r in dr:
            if (r["team_a"]==ta or r["team_b"]==ta) and (r["team_a"]==tb or r["team_b"]==tb): return r
    return None

# ═══════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    # ── CONTEST SWITCHER (top of sidebar) ──
    st.markdown("## 🏆 Contest")
    contest_ids = list(st.session_state.contests.keys())
    contest_labels = {cid: st.session_state.contests[cid].get("contest_name", cid) for cid in contest_ids}

    selected_cid = st.selectbox("Active contest", contest_ids,
        index=contest_ids.index(st.session_state.active_contest) if st.session_state.active_contest in contest_ids else 0,
        format_func=lambda x: f"{contest_labels[x]} ({st.session_state.contests[x].get('total_entries', '?')} entries)",
        key="contest_selector")

    if selected_cid != st.session_state.active_contest:
        st.session_state.active_contest = selected_cid
        st.session_state.sim_results = None
        st.rerun()

    C = ctx()  # Refresh after potential switch

    # Contest name editor
    new_name = st.text_input("Contest name", value=C.get("contest_name", ""), key="cname_input")
    if new_name != C.get("contest_name", ""):
        C["contest_name"] = new_name

    # Add / remove contests
    col_add, col_del = st.columns(2)
    with col_add:
        if st.button("➕ Add Contest", use_container_width=True):
            new_id = f"contest_{len(st.session_state.contests)+1}"
            while new_id in st.session_state.contests:
                new_id += "_"
            st.session_state.contests[new_id] = {
                "contest_name": f"Contest {len(st.session_state.contests)+1}",
                "total_entries": 100, "my_entries": 1, "pick_counts": {}, "my_picks": {}
            }
            st.session_state.active_contest = new_id
            st.session_state.sim_results = None
            st.rerun()
    with col_del:
        if len(st.session_state.contests) > 1:
            if st.button("🗑️ Remove", use_container_width=True):
                del st.session_state.contests[st.session_state.active_contest]
                st.session_state.active_contest = list(st.session_state.contests.keys())[0]
                st.session_state.sim_results = None
                st.rerun()

    st.markdown("---")
    st.markdown("## ⚙️ Contest Settings")
    C["total_entries"] = st.number_input("Pool entries remaining", 1, 50000, C.get("total_entries", 900), 1)
    C["my_entries"] = st.number_input("My entries remaining", 0, 20, C.get("my_entries", 3), 1)

    st.markdown("---")
    st.markdown("## 🔬 Sim Settings")
    st.session_state.n_sims = st.number_input("Sims per pick", 100, 50000, st.session_state.n_sims, 100)

    st.markdown("---")
    st.markdown("## 📅 Active Day")
    current_day = st.selectbox("Day", TOURNAMENT_DAYS, index=st.session_state.current_day_idx,
                                format_func=lambda x: f"{x} — {ROUND_NAMES[x]}")
    st.session_state.current_day_idx = TOURNAMENT_DAYS.index(current_day)

    st.markdown("---")
    st.markdown("## 📡 ESPN Status")
    nr = sum(len(v) for v in espn_results.values()); nw = len(api_winners)
    if nr: st.success(f"{nr} games · {nw} winners")
    else: st.info("No completed games yet")

    st.markdown("---")
    st.markdown("## 🔧 Override Winner")
    all_gids = list(FIRST_ROUND.keys()) + [k for k in BRACKET_TREE if live_bracket.get(k,{}).get("teams_known")]
    og = st.selectbox("Game", ["(none)"] + all_gids, key="osel")
    if og != "(none)":
        g = live_bracket.get(og, {})
        ow = st.radio("Winner", [g.get("team_a","?"), g.get("team_b","?")], horizontal=True, key="ow")
        if st.button("Set"): st.session_state.manual_winners[og] = ow; st.rerun()

    st.markdown("---")
    st.markdown("## 💾 Save / Load")
    if os.path.exists(SAVE_FILE):
        mod_time = datetime.fromtimestamp(os.path.getmtime(SAVE_FILE))
        st.caption(f"Last saved: {mod_time.strftime('%b %d, %I:%M %p')}")
    if st.button("💾 Save Now", use_container_width=True):
        if save_state(): st.success("Saved!")
    export_json = export_state_json()
    st.download_button("📤 Export All Contests", data=export_json,
        file_name=f"survivor_state_{date.today().strftime('%Y%m%d')}.json",
        mime="application/json", use_container_width=True)
    uploaded = st.file_uploader("📥 Import", type=["json"], key="import_file")
    if uploaded is not None:
        if import_state_json(uploaded.read().decode("utf-8")):
            st.success("Imported!"); st.rerun()
    if st.button("🗑️ Reset All Data", use_container_width=True):
        st.session_state.confirm_reset = True
    if st.session_state.get("confirm_reset"):
        st.warning("Erase ALL contests and settings?")
        cy, cn = st.columns(2)
        with cy:
            if st.button("Yes, reset"):
                for k in list(st.session_state.keys()): del st.session_state[k]
                if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
                st.rerun()
        with cn:
            if st.button("Cancel"): st.session_state.confirm_reset = False; st.rerun()

# ═══════════════════════════════════════════════════════════
#  MAIN — Header with contest name
# ═══════════════════════════════════════════════════════════
st.title("🏀 March Madness Survivor Engine")
st.markdown(f"### 🏆 {C.get('contest_name', 'Contest')} — {C.get('total_entries', 0)} entries · {C.get('my_entries', 0)} of mine")

c1,c2,c3,c4 = st.columns(4)
c1.metric("Day", current_day); c2.metric("Round", ROUND_NAMES[current_day])
c3.metric("Pool Size", C.get("total_entries", 0)); c4.metric("Eliminated", len(eliminated))

tab_games, tab_picks, tab_sweat, tab_recs, tab_bracket, tab_detail = st.tabs([
    "📋 Games & Spreads", "📊 Pick Tracking", "🔥 Sweat Board",
    "🎯 Recommendations", "🏟️ Bracket", "📐 Methodology"
])

# ═══════════════════════════════════════════════════════════
#  TAB 1: GAMES & SPREADS (shared — spreads don't change between contests)
# ═══════════════════════════════════════════════════════════
with tab_games:
    st.markdown(f"### {current_day} — {ROUND_NAMES[current_day]}")
    tg = {gid:g for gid,g in live_bracket.items() if g.get("day")==current_day}
    if tg:
        for gid, g in sorted(tg.items(), key=lambda x: x[1].get("time","")):
            ta,tb = g["team_a"],g["team_b"]
            ok = f"spread_{gid}"
            cs = st.session_state.spread_overrides.get(ok, g.get("spread"))
            fe = "🔴" if ta in eliminated else ("🏆" if gid in all_winners and all_winners[gid]==ta else "🟢")
            de = "🔴" if tb in eliminated else ("🏆" if gid in all_winners and all_winners[gid]==tb else "🟢")
            live = get_live_info(ta, tb); ls = ""
            if live:
                if live["is_live"]: ls = f" 🔴 LIVE {live['score_a']}-{live['score_b']} ({live['detail']})"
                elif live["is_final"]: ls = f" ✅ FINAL {live['score_a']}-{live['score_b']}"
            x1,x2,x3 = st.columns([1,3,2])
            with x1: st.markdown(f"**{g.get('time','TBD')}**"); st.caption(g.get("loc","TBD"))
            with x2:
                sas = f"({g['seed_a']}) " if g.get("seed_a") else ""
                sbs = f"({g['seed_b']}) " if g.get("seed_b") else ""
                st.markdown(f"{fe} **{sas}{ta}** vs {de} **{sbs}{tb}**{ls}")
            with x3:
                sv = float(cs) if cs is not None else 0.0
                ns = st.number_input("Spread", value=sv, step=0.5, key=f"sp_{gid}", label_visibility="collapsed")
                st.session_state.spread_overrides[ok] = ns
                wp_ = win_prob(ns)
                bar = f'<div style="display:flex;height:20px;border-radius:4px;overflow:hidden;font-size:11px"><div style="width:{wp_*100:.0f}%;background:#2ecc71;color:white;text-align:center;font-weight:bold">{ta[:10]} {wp_:.0%}</div><div style="width:{(1-wp_)*100:.0f}%;background:#e74c3c;color:white;text-align:center;font-weight:bold">{tb[:10]} {1-wp_:.0%}</div></div>'
                st.markdown(bar, unsafe_allow_html=True)
            st.markdown("---")
    else: st.info("No games for this day yet.")

# ═══════════════════════════════════════════════════════════
#  TAB 2: PICK TRACKING (per-contest)
# ═══════════════════════════════════════════════════════════
with tab_picks:
    st.markdown(f"### 📊 Pick Tracking — {C.get('contest_name', 'Contest')}")
    pick_tab_day = st.selectbox("Day to enter picks for", TOURNAMENT_DAYS,
        index=st.session_state.current_day_idx,
        format_func=lambda x: f"{x} — {ROUND_NAMES[x]}", key="pick_tab_day")
    day_games = {gid:g for gid,g in live_bracket.items() if g.get("day")==pick_tab_day}
    pc = C.get("pick_counts", {})
    if day_games:
        st.markdown("#### Pool Pick Counts")
        for gid, g in sorted(day_games.items(), key=lambda x: x[1].get("time","")):
            ta, tb = g["team_a"], g["team_b"]
            if "W(" in ta or "W(" in tb: continue
            sas = f"({g['seed_a']}) " if g.get("seed_a") else ""
            sbs = f"({g['seed_b']}) " if g.get("seed_b") else ""
            ca, cb = st.columns(2)
            with ca:
                ka = f"{pick_tab_day}|{ta}"
                na = st.number_input(f"{sas}{ta}", 0, C["total_entries"], pc.get(ka,0), 1, key=f"pc_{ka}")
                pc[ka] = na
            with cb:
                kb = f"{pick_tab_day}|{tb}"
                nb = st.number_input(f"{sbs}{tb}", 0, C["total_entries"], pc.get(kb,0), 1, key=f"pc_{kb}")
                pc[kb] = nb
        C["pick_counts"] = pc
        st.markdown("---")
        total_today = sum(pc.get(f"{pick_tab_day}|{t}", 0) for t in ALL_TEAMS)
        st.metric("Total picks entered", total_today)
        if total_today > 0 and total_today != C["total_entries"]:
            st.warning(f"Total ({total_today}) ≠ pool size ({C['total_entries']}). Fine if some entries already eliminated.")
        pick_data = []
        for gid, g in sorted(day_games.items(), key=lambda x: x[1].get("time","")):
            ta, tb = g["team_a"], g["team_b"]
            if "W(" in ta: continue
            for t, s in [(ta, g.get("seed_a")), (tb, g.get("seed_b"))]:
                cnt = pc.get(f"{pick_tab_day}|{t}", 0)
                pick_data.append({"Team":t,"Seed":s,"Picks":cnt,
                    "Pick%":cnt/max(total_today,1)*100,"Opponent":tb if t==ta else ta})
        if pick_data: st.dataframe(pd.DataFrame(pick_data).sort_values("Picks",ascending=False), use_container_width=True, hide_index=True,
            column_config={"Pick%": st.column_config.NumberColumn(format="%.1f%%")})
    else: st.info("No games for this day yet.")

    # My Picks
    st.markdown("---")
    st.markdown(f"### 🎯 My Picks — {C.get('contest_name','')}")
    mp = C.get("my_picks", {})
    for en in range(1, C.get("my_entries", 0) + 1):
        st.markdown(f"#### Entry #{en}")
        cols = st.columns(min(len(TOURNAMENT_DAYS), 5))
        for i, day in enumerate(TOURNAMENT_DAYS):
            with cols[i % len(cols)]:
                pick_key = f"{en}|{day}"
                dgp = {gid:g for gid,g in live_bracket.items() if g.get("day")==day}
                used_prior = set()
                for pd_day in TOURNAMENT_DAYS:
                    if pd_day == day: break
                    pk = f"{en}|{pd_day}"
                    if mp.get(pk): used_prior.add(mp[pk])
                teams_today = []
                for g in dgp.values():
                    for t in [g["team_a"], g["team_b"]]:
                        if "W(" not in t and "/" not in t and t not in eliminated: teams_today.append(t)
                options = ["—"] + [t for t in sorted(teams_today) if t not in used_prior]
                cur = mp.get(pick_key, "—")
                if cur and cur != "—" and cur not in options: options.append(cur)
                if cur not in options: cur = "—"
                sel = st.selectbox(f"{day}", options, index=options.index(cur), key=f"mp_{st.session_state.active_contest}_{pick_key}")
                mp[pick_key] = sel if sel != "—" else ""
        # Update used_teams
        used = set()
        for day in TOURNAMENT_DAYS:
            if mp.get(f"{en}|{day}"): used.add(mp[f"{en}|{day}"])
        st.session_state.used_teams[f"{st.session_state.active_contest}_{en}"] = used
    C["my_picks"] = mp

    # Availability tracker
    st.markdown("---")
    st.markdown("### 📈 Entries Still Available Per Team")
    avail_day = st.selectbox("As of", TOURNAMENT_DAYS, index=st.session_state.current_day_idx,
        format_func=lambda x: f"{x} — {ROUND_NAMES[x]}", key="avail_day")
    avail_idx = TOURNAMENT_DAYS.index(avail_day)
    avail_rows = []
    for team in ALL_TEAMS:
        if team in eliminated: continue
        seed = get_team_seed(team)
        total_used = sum(pc.get(f"{TOURNAMENT_DAYS[d]}|{team}", 0) for d in range(avail_idx))
        remaining = max(C["total_entries"] - total_used, 0)
        avail_rows.append({"Team":team,"Seed":seed,"Times Picked":total_used,
            "Entries Still Have":remaining,"% Available":remaining/max(C['total_entries'],1)*100})
    if avail_rows: st.dataframe(pd.DataFrame(avail_rows).sort_values("Times Picked",ascending=False), use_container_width=True, hide_index=True,
        column_config={"% Available": st.column_config.NumberColumn(format="%.1f%%")})

# ═══════════════════════════════════════════════════════════
#  TAB 3: SWEAT BOARD (per-contest)
# ═══════════════════════════════════════════════════════════
with tab_sweat:
    st.markdown(f"### 🔥 Sweat Board — {C.get('contest_name','')}")
    sweat_day = st.selectbox("Day", TOURNAMENT_DAYS, index=st.session_state.current_day_idx,
        format_func=lambda x: f"{x} — {ROUND_NAMES[x]}", key="sweat_day")
    mp = C.get("my_picks", {})
    my_picks_today = {}
    for en in range(1, C.get("my_entries", 0) + 1):
        pick = mp.get(f"{en}|{sweat_day}", "")
        if pick: my_picks_today[en] = pick
    if my_picks_today:
        st.markdown("**My picks today:** " + " | ".join([f"Entry #{en}: **{p}**" for en, p in my_picks_today.items()]))
    else: st.caption("No picks entered yet.")
    st.markdown("---")
    day_games = {gid:g for gid,g in live_bracket.items() if g.get("day")==sweat_day}
    pc = C.get("pick_counts", {})
    total_picks_day = sum(pc.get(f"{sweat_day}|{t}", 0) for g in day_games.values() for t in [g["team_a"],g["team_b"]] if "W(" not in t)
    if day_games:
        for gid, g in sorted(day_games.items(), key=lambda x: x[1].get("time","")):
            ta, tb = g["team_a"], g["team_b"]
            if "W(" in ta: continue
            sas = f"({g['seed_a']})" if g.get("seed_a") else ""
            sbs = f"({g['seed_b']})" if g.get("seed_b") else ""
            cnt_a = pc.get(f"{sweat_day}|{ta}", 0); cnt_b = pc.get(f"{sweat_day}|{tb}", 0)
            pct_a = f"{cnt_a/max(total_picks_day,1):.1%}" if total_picks_day > 0 else "—"
            pct_b = f"{cnt_b/max(total_picks_day,1):.1%}" if total_picks_day > 0 else "—"
            mpa = [en for en, pk in my_picks_today.items() if pk == ta]
            mpb = [en for en, pk in my_picks_today.items() if pk == tb]
            live = get_live_info(ta, tb)
            score_a = score_b = "—"; status_text = "🔜 Upcoming"
            if live:
                score_a = str(live["score_a"]); score_b = str(live["score_b"])
                if live["is_live"]: status_text = f"🔴 {live['detail']}"
                elif live["is_final"]: status_text = "✅ FINAL"
            ea = ta in eliminated; eb = tb in eliminated
            wa = gid in all_winners and all_winners[gid]==ta
            wb = gid in all_winners and all_winners[gid]==tb
            def th(team, ss, cnt, pct, mine, elim, won, score, elist):
                bg = ""
                if mine and won: bg="background:linear-gradient(90deg,#27ae60,#2ecc71);color:white;"
                elif mine and elim: bg="background:linear-gradient(90deg,#c0392b,#e74c3c);color:white;"
                elif mine: bg="background:linear-gradient(90deg,#2980b9,#3498db);color:white;"
                td = "text-decoration:line-through;opacity:0.5;" if elim else ""
                ic = "🏆" if won else ("❌" if elim else "")
                mb = ""
                if mine: mb=f'<span style="background:#f39c12;color:white;padding:1px 6px;border-radius:10px;font-size:10px;margin-left:4px">MY PICK {", ".join(f"#{e}" for e in elist)}</span>'
                return f'<div style="padding:8px 12px;border-radius:6px;margin:2px 0;{bg}"><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-weight:bold;font-size:16px;{td}">{ic} {ss} {team}{mb}</span><span style="font-size:20px;font-weight:bold">{score}</span></div><div style="font-size:12px;opacity:0.8">Picks: {cnt} ({pct})</div></div>'
            html = f'<div style="border:1px solid #333;border-radius:8px;padding:8px;margin-bottom:12px"><div style="text-align:center;font-size:11px;color:#888;margin-bottom:4px">{g.get("time","TBD")} · {g.get("loc","TBD")} · {status_text}</div>{th(ta,sas,cnt_a,pct_a,len(mpa)>0,ea,wa,score_a,mpa)}{th(tb,sbs,cnt_b,pct_b,len(mpb)>0,eb,wb,score_b,mpb)}</div>'
            st.markdown(html, unsafe_allow_html=True)
    else: st.info("No games for this day yet.")
    st.markdown("---")
    st.markdown("### 📊 Entry Survival Status")
    for en in range(1, C.get("my_entries", 0) + 1):
        alive = True; picks_made = []
        for day in TOURNAMENT_DAYS:
            pick = mp.get(f"{en}|{day}", "")
            if pick:
                lost = pick in eliminated
                picks_made.append(f"{'❌' if lost else '✅'} {day}: {pick}")
                if lost: alive = False
        st.markdown(f"**Entry #{en} — {'🟢 ALIVE' if alive else '🔴 ELIMINATED'}**")
        st.caption(" | ".join(picks_made) if picks_made else "No picks made yet")

# ═══════════════════════════════════════════════════════════
#  TAB 4: RECOMMENDATIONS (per-contest)
# ═══════════════════════════════════════════════════════════
with tab_recs:
    st.markdown(f"### 🎯 Recommendations — {C.get('contest_name','')}")
    st.markdown("**🛡️ Safety** (survive today, preserve assets) and **⚡ Leverage** (contrarian edge, +EV)")
    tg = {gid:g for gid,g in live_bracket.items() if g.get("day")==current_day}
    pc = C.get("pick_counts", {}); mp = C.get("my_picks", {})
    if tg:
        at = []
        for gid, g in tg.items():
            ok=f"spread_{gid}"; sp=st.session_state.spread_overrides.get(ok, g.get("spread") or 0); wp_=win_prob(sp)
            if g["team_a"] not in eliminated and "W(" not in g["team_a"]:
                at.append({"team":g["team_a"],"seed":g.get("seed_a"),"win_prob":wp_,"opponent":g["team_b"],"spread":sp,"region":g["region"]})
            if g["team_b"] not in eliminated and "W(" not in g["team_b"]:
                at.append({"team":g["team_b"],"seed":g.get("seed_b"),"win_prob":1-wp_,"opponent":g["team_a"],"spread":-sp,"region":g["region"]})
        opp = compute_opp_pct_model(at, st.session_state.current_day_idx, len(TOURNAMENT_DAYS), pc, current_day, C["total_entries"])
        has_actual = any(pc.get(f"{current_day}|{t['team']}", 0) > 0 for t in at)
        if has_actual: st.success("✅ Using **actual pick data**")
        else: st.info("📊 Using **modeled opponent behavior** (enter picks in Pick Tracking for real data)")
        fdt = []
        for fi in range(st.session_state.current_day_idx+1, min(st.session_state.current_day_idx+5, len(TOURNAMENT_DAYS))):
            fd=TOURNAMENT_DAYS[fi]; fg={gid:g for gid,g in live_bracket.items() if g.get("day")==fd}; fa=[]
            for gid,g in fg.items():
                ok=f"spread_{gid}"; sp=st.session_state.spread_overrides.get(ok,g.get("spread") or 0); wp_=win_prob(sp)
                if g["team_a"] not in eliminated and "W(" not in g["team_a"]: fa.append({"team":g["team_a"],"win_prob":wp_,"seed":g.get("seed_a"),"region":g.get("region")})
                if g["team_b"] not in eliminated and "W(" not in g["team_b"]: fa.append({"team":g["team_b"],"win_prob":1-wp_,"seed":g.get("seed_b"),"region":g.get("region")})
            fdt.append(fa)
        if st.button("🚀 Run Simulation Engine", type="primary", use_container_width=True):
            prog = st.progress(0, "Running..."); ar = {}
            for en in range(1, C.get("my_entries",0)+1):
                used = st.session_state.used_teams.get(f"{st.session_state.active_contest}_{en}", set())
                ea = [t for t in at if t["team"] not in used]; res = []
                for idx, ti in enumerate(ea):
                    pv = ((en-1)*len(ea)+idx)/max(C["my_entries"]*len(ea),1)
                    prog.progress(min(pv,1.0), f"Entry #{en}: {ti['team']}...")
                    sv = sim_survivor(ti["team"], ea, fdt, st.session_state.n_sims, st.session_state.current_day_idx, len(TOURNAMENT_DAYS), used, pc, C["total_entries"])
                    op = opp.get(ti["team"], 0)
                    fv = compute_future_value(ti["seed"], ti["win_prob"], st.session_state.current_day_idx, len(TOURNAMENT_DAYS))
                    ac = compute_entries_with_team_available(ti["team"], st.session_state.current_day_idx, pc, C["total_entries"])
                    rp = compute_region_penalty(ti.get("region"), used, st.session_state.current_day_idx, len(TOURNAMENT_DAYS))
                    sc = compute_scarcity_factor(ti["team"], used, fdt, eliminated)
                    dc = compute_day_conflicts(ti["team"], used)
                    # Day conflicts in E8/FF apply a penalty
                    day_pen = 0.5 if dc else 1.0
                    safety = compute_safety_score(ti["win_prob"], fv, sv, rp, sc) * day_pen
                    lev = compute_leverage_score(ti["win_prob"], op, fv, sv, rp, sc) * day_pen
                    sched = get_team_schedule(ti["team"])
                    res.append({"Team":ti["team"],"Seed":ti["seed"],"Region":ti["region"],"Opponent":ti["opponent"],"Spread":ti["spread"],"Win%":ti["win_prob"],"Opp Pick%":op,"Future Value":fv,"Entries Avail":ac,"Survival":sv,"Rgn Pen":rp,"Scarcity":sc,"Safety":safety,"Leverage":lev,
                        "E8 Day":sched.get("E8","?"),"Day Warn":"⚠️" if dc else "✅"})
                ar[en] = res
            prog.progress(1.0,"Done!"); st.session_state.sim_results = ar; time.sleep(0.3); prog.empty()
        if st.session_state.sim_results:
            for en, res in st.session_state.sim_results.items():
                st.markdown(f"#### Entry #{en}")
                used = st.session_state.used_teams.get(f"{st.session_state.active_contest}_{en}", set())
                if used: st.caption(f"Already used: {', '.join('~~'+t+'~~' if t in eliminated else t for t in sorted(used))}")

                # Championship feasibility check
                feasible, champ_warn = check_championship_feasibility(used)
                if not feasible:
                    st.error(champ_warn)

                if not res: st.warning("No teams available."); continue
                sr = sorted([r for r in res if r["Win%"]>=MIN_WP_SAFETY], key=lambda x: x["Safety"], reverse=True)
                lr = sorted([r for r in res if r["Win%"]>=MIN_WP_LEVERAGE], key=lambda x: x["Leverage"], reverse=True)
                ts = sr[0] if sr else None
                tl = None
                if lr:
                    for lp in lr:
                        if not ts or lp["Team"] != ts["Team"]: tl = lp; break
                    if tl is None: tl = lr[0]
                def pcard(p, label, color, icon, sn, sk):
                    if not p: return f'<div style="border:1px solid #555;border-radius:8px;padding:12px;opacity:0.5">No {label.lower()} available</div>'
                    rgn_warn = f' · <span style="color:#e74c3c">⚠ Rgn:{p.get("Rgn Pen",1):.0%}</span>' if p.get("Rgn Pen",1) < 1 else ""
                    scar_warn = f' · <span style="color:#e67e22">⚠ Thin:{p.get("Scarcity",1):.0%}</span>' if p.get("Scarcity",1) < 1 else ""
                    day_warn = f' · <span style="color:#e74c3c">⚠ Day conflict</span>' if p.get("Day Warn")=="⚠️" else ""
                    e8d = p.get("E8 Day","?")
                    return f'<div style="border:2px solid {color};border-radius:8px;padding:12px;background:rgba({",".join(str(int(color.lstrip("#")[i:i+2],16)) for i in (0,2,4))},0.1)"><div style="font-size:13px;color:{color};font-weight:bold">{icon} {label}</div><div style="font-size:22px;font-weight:bold;margin:4px 0">({p["Seed"]}) {p["Team"]}</div><div style="font-size:13px;opacity:0.9">vs {p["Opponent"]} · Spread: {p["Spread"]:+.1f} · {p["Region"]} · E8: {e8d}</div><div style="font-size:12px;margin-top:8px;line-height:1.6">Win: <b>{p["Win%"]:.0%}</b> · Opp: <b>{p["Opp Pick%"]:.1%}</b> · FV: <b>{p["Future Value"]:.2f}</b><br>Surv: <b>{p["Survival"]:.0%}</b> · Avail: <b>{p["Entries Avail"]}</b>{rgn_warn}{scar_warn}{day_warn}<br><span style="font-size:14px"><b>{sn}: {p[sk]:.3f}</b></span></div></div>'
                cs, cl = st.columns(2)
                with cs: st.markdown(pcard(ts,"SAFETY PICK","#2ecc71","🛡️","Safety","Safety"), unsafe_allow_html=True)
                with cl: st.markdown(pcard(tl,"LEVERAGE PICK","#f39c12","⚡","Leverage","Leverage"), unsafe_allow_html=True)
                if ts and tl and ts["Team"]==tl["Team"]:
                    st.info(f"🎯 Both converge on **{ts['Team']}**. Showing alternatives:")
                    a2s = sr[1] if len(sr)>1 else None
                    a2l = next((lp for lp in lr if lp["Team"]!=tl["Team"] and (not a2s or lp["Team"]!=a2s["Team"])), None)
                    ca, cb = st.columns(2)
                    with ca:
                        if a2s: st.markdown(pcard(a2s,"SAFETY ALT","#27ae60","🛡️","Safety","Safety"), unsafe_allow_html=True)
                    with cb:
                        if a2l: st.markdown(pcard(a2l,"LEVERAGE ALT","#e67e22","⚡","Leverage","Leverage"), unsafe_allow_html=True)
                else:
                    with st.expander("📋 Runner-ups"):
                        ca, cb = st.columns(2)
                        with ca:
                            if len(sr)>1: st.markdown(pcard(sr[1],"SAFETY #2","#27ae60","🛡️","Safety","Safety"), unsafe_allow_html=True)
                        with cb:
                            a2l = next((lp for lp in lr if lp["Team"]!=(tl["Team"] if tl else "") and lp["Team"]!=(ts["Team"] if ts else "")), None)
                            if a2l: st.markdown(pcard(a2l,"LEVERAGE #2","#e67e22","⚡","Leverage","Leverage"), unsafe_allow_html=True)
                st.markdown("##### Full Rankings")
                sc = st.radio("Sort by", ["Safety","Leverage","Win%","Future Value","Rgn Pen","Scarcity"], horizontal=True, key=f"sort_{en}")
                df = pd.DataFrame(res).sort_values(sc, ascending=(sc=="Future Value"))
                # Convert 0-1 probabilities to 0-100 for display
                for pct_col in ["Win%", "Opp Pick%", "Survival"]:
                    df[pct_col] = df[pct_col] * 100
                st.dataframe(df, use_container_width=True, hide_index=True,
                    column_config={
                        "Win%": st.column_config.NumberColumn(format="%.1f%%"),
                        "Opp Pick%": st.column_config.NumberColumn(format="%.1f%%"),
                        "Future Value": st.column_config.NumberColumn(format="%.2f"),
                        "Survival": st.column_config.NumberColumn(format="%.1f%%"),
                        "Rgn Pen": st.column_config.NumberColumn("Region", format="%.2f", help="Region diversity penalty (1.0=good, <1=already used this region)"),
                        "Scarcity": st.column_config.NumberColumn(format="%.2f", help="Future options remaining (1.0=plenty, <1=running thin)"),
                        "Safety": st.column_config.NumberColumn(format="%.3f"),
                        "Leverage": st.column_config.NumberColumn(format="%.3f"),
                        "Spread": st.column_config.NumberColumn(format="%+.1f"),
                        "E8 Day": st.column_config.TextColumn("E8 Day", help="Which day this team's region plays in the Elite 8"),
                        "Day Warn": st.column_config.TextColumn("Sched", help="⚠️ = day conflict with existing picks in E8/FF"),
                    }); st.markdown("---")
            st.markdown("""### 📝 How to Read This
**🛡️ Safety** — Survive today without wasting a premium asset, while staying diversified across regions.
**⚡ Leverage** — Best contrarian play that's +EV. Guaranteed to be a different team than Safety.
Close-game picks (7-10 seeds) with near-zero ownership rank highest — true leverage is going where nobody else goes.

**Key columns:**
- **E8 Day**: When this team's region plays in the Elite 8 (Sat 3/28 or Sun 3/29). Pair picks from opposite E8 days.
- **Day Warn**: ⚠️ = picking this team creates a day conflict with prior picks in the E8 or Final Four.
- **Region / Rgn Pen**: Avoid stacking picks from one region. Only 1 team per region reaches the Final Four.
- **Scarcity**: 1.00 = plenty of future options. <1.00 = picking this team leaves you thin later.
- **Future Value** (0-1): how valuable is it to SAVE this team for later rounds?

**Schedule pairing (CRITICAL for E8+):**
- South & West play E8 on **Saturday 3/28** · East & Midwest play E8 on **Sunday 3/29**
- FF: East vs South, West vs Midwest. If you use both East + South in E8 → no championship pick possible.
- **Valid E8 combos**: East+West, East+Midwest, South+West, South+Midwest
- **Invalid E8 combos**: East+South ❌, West+Midwest ❌ (they play each other in the FF)

**When to use which:** Ahead → Leverage. Behind → Safety. Both agree → strong signal.""")
        else: st.info("Click **Run Simulation Engine** to generate picks.")
    else: st.info("No games for this day yet.")

# ═══════════════════════════════════════════════════════════
#  TAB 5: BRACKET
# ═══════════════════════════════════════════════════════════
with tab_bracket:
    st.markdown("### 🏟️ Live Bracket")
    rl = {"R1":"Round of 64","R2":"Round of 32","S16":"Sweet 16","E8":"Elite 8","FF":"Final Four","CHAMP":"Championship"}
    for rnd in ["R1","R2","S16","E8","FF","CHAMP"]:
        rg = {gid:g for gid,g in live_bracket.items() if get_round(gid)==rnd}
        if not rg: continue
        st.markdown(f"#### {rl[rnd]}"); rows = []
        for gid,g in sorted(rg.items()):
            ta,tb = g["team_a"],g["team_b"]
            sa="❌" if ta in eliminated else ("🏆" if gid in all_winners and all_winners[gid]==ta else "✅")
            sb_="❌" if tb in eliminated else ("🏆" if gid in all_winners and all_winners[gid]==tb else "✅")
            sp=st.session_state.spread_overrides.get(f"spread_{gid}",g.get("spread"))
            rows.append({"Day":g.get("day","TBD"),"Region":g.get("region",""),
                "Team A":f"{sa} ({g['seed_a']}) {ta}" if g.get("seed_a") else f"{sa} {ta}",
                "Team B":f"{sb_} ({g['seed_b']}) {tb}" if g.get("seed_b") else f"{sb_} {tb}",
                "Spread":f"{sp:+.1f}" if sp is not None else "TBD","Winner":all_winners.get(gid,"—"),
                "Status":"✅" if gid in all_winners else ("⏳" if not g.get("teams_known",True) else "🔜")})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.markdown(f"**{len(eliminated)} eliminated:** {', '.join(sorted(eliminated)) if eliminated else 'None yet'}")

# ═══════════════════════════════════════════════════════════
#  TAB 6: METHODOLOGY
# ═══════════════════════════════════════════════════════════
with tab_detail:
    st.markdown("""### 📐 Methodology
#### Multi-Contest Support
Each contest has independent: pool size, entry count, pick counts, and personal picks. Spreads, game results, and sim settings are shared. Switch contests via the sidebar dropdown.
#### Auto-Update: ESPN API → bracket tree → future matchup generation
#### Win Probability: spread → normal CDF (σ = 11.0)""")
    st.dataframe(pd.DataFrame([{"Spread":f"{s:+.1f}","Win%":f"{win_prob(s):.1%}"} for s in [-1.5,-3.5,-6.5,-10.5,-16.5,-22.5,-27.5]]), hide_index=True)
    st.markdown("""#### Opponent Model
- **With actual data**: real pick counts from your pool
- **Modeled**: wp^4 power curve · hard 45% floor · seed-saving (1-seeds at 8% base in R1) · 4/5/6-seed chalk boost · brand boost
#### Future Value: seed premium × time remaining × alive probability (0.0-1.0)
#### Safety: `win_prob × (1 - 0.7×FV) × surv × region_pen × scarcity`
#### Leverage: `(1-opp)^1.5 × min(wp, 0.85)^0.5 × (1 - 0.7×FV) × surv^0.5 × region_pen × scarcity`
- Contrarian exponent 1.5: steep — 10% ownership ≫ 1% (rewards close-game picks)
- wp capped at 85% + sqrt: 99% and 59% close in score (leverage ≠ blowouts)
- FV penalty 70%: never burn premium teams early
#### Region Penalty: avoids stacking picks from one region (1 prior=0.85, 2=0.60, 3+=0.40)
#### Pick Scarcity: checks if picking this team leaves you with enough future options (0=death, 5+=fine)
#### Smart Sim: future rounds save 1/2 seeds + prefer underused regions""")

st.markdown("---")
st.caption("Survivor Engine v4.0 | Multi-contest | Smart sim + FV + Safety/Leverage | ESPN auto-update")
save_state()
