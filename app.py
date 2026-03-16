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
#  PERSISTENCE — Auto-save/load all manual data to JSON
# ═══════════════════════════════════════════════════════════
PERSISTED_KEYS = ["total_entries", "my_entries", "n_sims", "current_day_idx",
                  "spread_overrides", "manual_winners", "pick_counts", "my_picks"]

def save_state():
    """Save all persisted session state to a local JSON file."""
    data = {}
    for k in PERSISTED_KEYS:
        val = st.session_state.get(k)
        if val is not None:
            # Convert sets to lists for JSON serialization
            if isinstance(val, set):
                data[k] = list(val)
            elif isinstance(val, dict):
                data[k] = {str(dk): (list(dv) if isinstance(dv, set) else dv)
                           for dk, dv in val.items()}
            else:
                data[k] = val
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        return False

def load_state():
    """Load persisted state from JSON file. Returns dict or None."""
    if not os.path.exists(SAVE_FILE):
        return None
    try:
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
        return data
    except:
        return None

def export_state_json():
    """Export current state as a JSON string for download."""
    data = {}
    for k in PERSISTED_KEYS:
        val = st.session_state.get(k)
        if val is not None:
            if isinstance(val, set):
                data[k] = list(val)
            elif isinstance(val, dict):
                data[k] = {str(dk): (list(dv) if isinstance(dv, set) else dv)
                           for dk, dv in val.items()}
            else:
                data[k] = val
    return json.dumps(data, indent=2)

def import_state_json(json_str):
    """Import state from a JSON string into session state."""
    try:
        data = json.loads(json_str)
        for k in PERSISTED_KEYS:
            if k in data:
                st.session_state[k] = data[k]
        # Also save to disk immediately
        save_state()
        return True
    except:
        return False

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

TOURNAMENT_DAYS = ["Thu 3/19","Fri 3/20","Sat 3/21","Sun 3/22","Thu 3/27","Fri 3/28",
                   "Sat 3/29","Sun 3/30","Sat 4/4","Mon 4/6"]
ROUND_NAMES = {"Thu 3/19":"Rd of 64 (Thu)","Fri 3/20":"Rd of 64 (Fri)",
    "Sat 3/21":"Rd of 32 (Sat)","Sun 3/22":"Rd of 32 (Sun)",
    "Thu 3/27":"Sweet 16 (Thu)","Fri 3/28":"Sweet 16 (Fri)",
    "Sat 3/29":"Elite 8 (Sat)","Sun 3/30":"Elite 8 (Sun)",
    "Sat 4/4":"Final Four","Mon 4/6":"Championship"}
DAY_TO_DATE = {"Thu 3/19":"20260319","Fri 3/20":"20260320","Sat 3/21":"20260321",
    "Sun 3/22":"20260322","Thu 3/27":"20260327","Fri 3/28":"20260328",
    "Sat 3/29":"20260329","Sun 3/30":"20260330","Sat 4/4":"20260404","Mon 4/6":"20260406"}
REGION_DAY_R2 = {"East":"Sat 3/21","West":"Sun 3/22","Midwest":"Sun 3/22","South":"Sat 3/21"}
REGION_DAY_S16 = {"East":"Thu 3/27","West":"Fri 3/28","Midwest":"Fri 3/28","South":"Thu 3/27"}
REGION_DAY_E8 = {"East":"Sat 3/29","West":"Sun 3/30","Midwest":"Sun 3/30","South":"Sat 3/29"}

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
#  PICK TRACKING & OPPONENT MODELING
# ═══════════════════════════════════════════════════════════
def get_all_teams():
    """Get sorted list of all teams in the bracket."""
    teams = set()
    for g in FIRST_ROUND.values():
        for t in [g["team_a"], g["team_b"]]:
            if "/" not in t: teams.add(t)
    return sorted(teams)

def get_team_seed(team):
    """Look up seed for a team."""
    for g in FIRST_ROUND.values():
        if g["team_a"] == team: return g["seed_a"]
        if g["team_b"] == team: return g["seed_b"]
    return None

def compute_entries_with_team_available(team, day_idx, pick_counts, total_entries):
    """
    Given actual pick counts per day, compute how many entries still have
    this team available (haven't used it yet in a prior day).
    """
    used_on_team = 0
    for d_idx in range(day_idx):
        day = TOURNAMENT_DAYS[d_idx]
        key = f"{day}|{team}"
        used_on_team += pick_counts.get(key, 0)
    return max(total_entries - used_on_team, 0)

def compute_opp_pct_model(avail, rd_idx, total_rds, pick_counts, current_day, total_entries):
    """
    Hybrid model: use actual pick data if available for current day,
    otherwise fall back to the seed/brand model for future days.
    """
    if not avail: return {}

    # Check if we have actual data for today
    has_actual = any(pick_counts.get(f"{current_day}|{t['team']}", 0) > 0 for t in avail)

    if has_actual:
        result = {}
        total_picks = sum(pick_counts.get(f"{current_day}|{t['team']}", 0) for t in avail)
        for t in avail:
            cnt = pick_counts.get(f"{current_day}|{t['team']}", 0)
            result[t["team"]] = cnt / max(total_picks, 1)
        return result

    # Fallback: modeled behavior
    BRAND = {"Duke","Kansas","UConn","Michigan","Florida","Arizona","Kentucky","North Carolina",
             "Gonzaga","Houston","Purdue","Michigan State","Alabama","Iowa State","Illinois",
             "Arkansas","Virginia","UCLA","Louisville","St. John's","Tennessee"}
    scores = {}; rr = total_rds - rd_idx
    for t in avail:
        wp=t["win_prob"]; seed=t.get("seed") or 8
        base=wp**1.5
        if rr>3: d={1:0.15,2:0.25,3:0.45}.get(seed, 0.7 if seed<=5 else 1.0)
        elif rr>1: d={1:0.4,2:0.6}.get(seed, 1.0)
        else: d=1.0
        b=1.2 if t["team"] in BRAND else 1.0
        scores[t["team"]]=base*d*b
    tot=sum(scores.values())
    if tot==0: return {t["team"]:1/len(scores) for t in avail}
    return {t:s/tot for t,s in scores.items()}

# ═══════════════════════════════════════════════════════════
#  SIMULATION ENGINE v2 — Smart future play + replacement cost
# ═══════════════════════════════════════════════════════════
def win_prob(spread):
    if spread is None: return 0.5
    return float(norm.cdf(-spread / SPREAD_SIGMA))

def compute_future_value(seed, wp, rd_idx, total_rds):
    """
    How valuable is SAVING this team for future rounds?
    Returns 0.0 to 1.0. Higher = save this team, don't burn it today.

    Core insight: a 1-seed's value comes from SCARCITY in later rounds.
    In Round 1 you have 32 teams to pick from. In the Elite 8 you have 4.
    The 1-seed is replaceable today (3/4/5 seeds at 75-90%) but irreplaceable
    in the E8 where your alternatives might be 55-65%.
    """
    if seed is None: seed = 8
    rounds_remaining = total_rds - rd_idx - 1
    if rounds_remaining <= 0:
        return 0.0  # Last day — use everything, no future

    # Seed premium: how irreplaceable is this team in later rounds?
    if seed == 1:   premium = 0.95
    elif seed == 2: premium = 0.82
    elif seed == 3: premium = 0.60
    elif seed == 4: premium = 0.40
    elif seed == 5: premium = 0.25
    elif seed <= 7: premium = 0.10
    else:           premium = 0.0   # 8+ seeds: no future premium, burn freely

    # Time scaling: more rounds remaining = higher value to save
    # Diminishing returns — saving for 8 rounds isn't 4x better than 4
    time_factor = min(rounds_remaining / 4.0, 1.0)

    # Survival probability: team must actually be alive later to have future value
    # A 1-seed that might lose today has less future value
    alive_factor = min(wp * 1.3, 1.0)

    return premium * time_factor * alive_factor

def smart_future_pick(available, rounds_remaining):
    """
    Pick the best team for a future sim round using seed-saving logic.
    Instead of always grabbing the highest win-prob (which is always a 1-seed),
    this models how a SMART player would actually play a survivor pool.
    """
    if not available:
        return None

    if rounds_remaining <= 1:
        # Last round: use your best team
        return max(available, key=lambda x: x["win_prob"])

    if rounds_remaining > 3:
        # Early/mid tournament: avoid 1-seeds and 2-seeds if possible
        mid_tier = [t for t in available if (t.get("seed") or 99) > 2]
        if mid_tier:
            return max(mid_tier, key=lambda x: x["win_prob"])

    if rounds_remaining > 1:
        # Mid tournament: avoid 1-seeds only
        non_top = [t for t in available if (t.get("seed") or 99) > 1]
        if non_top:
            return max(non_top, key=lambda x: x["win_prob"])

    # Fallback: use whatever is best
    return max(available, key=lambda x: x["win_prob"])

def sim_survivor(pick, avail_today, future_days, n, rd_idx, total_rds, used,
                 pick_counts, total_entries):
    """
    Monte Carlo with SMART future play.
    Future rounds use seed-aware strategy instead of pure greedy.
    """
    today_map = {t["team"]: t["win_prob"] for t in avail_today}
    if pick not in today_map: return 0.0

    survivals = 0
    for _ in range(n):
        ok = True; su = set(used); su.add(pick)

        # Today
        if np.random.random() >= today_map[pick]:
            ok = False
        elif future_days:
            # Future rounds: smart play
            for fi, ft in enumerate(future_days):
                rr = total_rds - (rd_idx + 1 + fi)  # rounds remaining after this future day
                av = [t for t in ft if t["team"] not in su]
                if not av:
                    ok = False; break
                best = smart_future_pick(av, rr)
                if best is None:
                    ok = False; break
                su.add(best["team"])
                if np.random.random() >= best["win_prob"]:
                    ok = False; break

        if ok: survivals += 1

    return survivals / max(n, 1)

def compute_safety_score(wp, future_value, survival):
    """
    SAFETY PICK: Maximize today's survival while preserving future assets.

    Formula: win_prob × (1 - 0.7 × future_value) × (0.3 + 0.7 × survival)

    - Heavily penalizes burning high-FV teams (70% discount on future value)
    - Still requires decent win probability
    - Survival provides a bonus but isn't dominant

    Examples (Round 1):
      Duke (99% wp, 0.95 FV, 85% surv) = 0.99 × 0.335 × 0.895 = 0.297
      Louisville (72% wp, 0.10 FV, 80% surv) = 0.72 × 0.930 × 0.860 = 0.576
      → Louisville wins. That's correct.
    """
    fv_penalty = 1.0 - 0.7 * future_value
    surv_factor = 0.3 + 0.7 * survival
    return wp * fv_penalty * surv_factor

def compute_leverage_score(wp, opp_pct, future_value, survival):
    """
    LEVERAGE PICK: Maximize contrarian edge while staying +EV.

    Formula: (1 - opp_pct)^0.6 × win_prob × (1 - 0.5 × future_value) × survival^0.5

    - Contrarian value is key (but sub-linear — 1% vs 5% matters less than 5% vs 20%)
    - Still requires solid win probability
    - Moderate future-value penalty (50% discount — willing to burn mid-seeds for big edge)
    - Survival has diminishing returns (square root)

    Examples (Round 1):
      Ohio State (59% wp, 12% opp, 0.0 FV, 70% surv) = 0.917 × 0.59 × 1.0 × 0.837 = 0.453
      Duke (99% wp, 2% opp, 0.95 FV, 85% surv) = 0.988 × 0.99 × 0.525 × 0.922 = 0.473
      Louisville (72% wp, 8% opp, 0.10 FV, 80% surv) = 0.951 × 0.72 × 0.95 × 0.894 = 0.582
      → Louisville wins leverage too. 8v9 games are viable contrarian plays.
    """
    contrarian = (1.0 - opp_pct) ** 0.6
    fv_penalty = 1.0 - 0.5 * future_value
    surv_factor = survival ** 0.5 if survival > 0 else 0
    return contrarian * wp * fv_penalty * surv_factor

# Minimum win probability thresholds
MIN_WP_SAFETY = 0.55     # Don't recommend safety picks below 55%
MIN_WP_LEVERAGE = 0.50   # Leverage can go slightly lower for big contrarian edge

# ═══════════════════════════════════════════════════════════
#  SESSION STATE INIT — Load from disk first, then defaults
# ═══════════════════════════════════════════════════════════
if "state_loaded" not in st.session_state:
    saved = load_state()
    if saved:
        for k in PERSISTED_KEYS:
            if k in saved:
                st.session_state[k] = saved[k]
    st.session_state.state_loaded = True

defaults = {
    "total_entries": 900, "my_entries": 3, "n_sims": 1000,
    "current_day_idx": 0, "spread_overrides": {}, "sim_results": None,
    "manual_winners": {},
    "pick_counts": {},      # key: "day|team" -> int
    "my_picks": {},         # key: "entry_num|day" -> team name
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v
if "used_teams" not in st.session_state:
    st.session_state.used_teams = {i: set() for i in range(1, 4)}

# ═══════════════════════════════════════════════════════════
#  FETCH & BUILD LIVE BRACKET
# ═══════════════════════════════════════════════════════════
with st.spinner("📡 Fetching ESPN results..."):
    espn_results = fetch_all()
    api_winners, api_losers = match_results(espn_results, FIRST_ROUND)

all_winners = {**api_winners, **st.session_state.manual_winners}
live_bracket = build_bracket(all_winners)

# Match later rounds too
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

# Helper: get espn live info for a matchup
def get_live_info(ta, tb):
    for dr in espn_results.values():
        for r in dr:
            if (r["team_a"]==ta or r["team_b"]==ta) and (r["team_a"]==tb or r["team_b"]==tb):
                return r
    return None

# ═══════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    st.session_state.total_entries = st.number_input("Pool entries remaining", 1, 10000, st.session_state.total_entries, 1)
    st.session_state.my_entries = st.number_input("My entries remaining", 0, 10, st.session_state.my_entries, 1)
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
    st.markdown("## 💾 Save / Load Data")

    # Auto-save status
    if os.path.exists(SAVE_FILE):
        mod_time = datetime.fromtimestamp(os.path.getmtime(SAVE_FILE))
        st.caption(f"Last saved: {mod_time.strftime('%b %d, %I:%M %p')}")
    else:
        st.caption("No save file yet")

    # Manual save button
    if st.button("💾 Save Now", use_container_width=True):
        if save_state():
            st.success("Saved!")
        else:
            st.error("Save failed")

    # Export for portability (Streamlit Cloud, new machine, etc.)
    export_json = export_state_json()
    st.download_button(
        "📤 Export Data (JSON)",
        data=export_json,
        file_name=f"survivor_state_{date.today().strftime('%Y%m%d')}.json",
        mime="application/json",
        use_container_width=True,
    )

    # Import
    uploaded = st.file_uploader("📥 Import Data (JSON)", type=["json"], key="import_file")
    if uploaded is not None:
        content = uploaded.read().decode("utf-8")
        if import_state_json(content):
            st.success("Imported! Refreshing...")
            st.rerun()
        else:
            st.error("Invalid file format")

    # Reset button
    if st.button("🗑️ Reset All Data", use_container_width=True):
        st.session_state.confirm_reset = True

    if st.session_state.get("confirm_reset"):
        st.warning("This will erase all picks, spreads, and settings.")
        col_y, col_n = st.columns(2)
        with col_y:
            if st.button("Yes, reset"):
                for k in PERSISTED_KEYS:
                    if k in st.session_state: del st.session_state[k]
                if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
                st.session_state.state_loaded = False
                st.session_state.confirm_reset = False
                st.rerun()
        with col_n:
            if st.button("Cancel"):
                st.session_state.confirm_reset = False
                st.rerun()

# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════
st.title("🏀 March Madness Survivor Engine")
c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Day", current_day); c2.metric("Round", ROUND_NAMES[current_day])
c3.metric("Pool Size", st.session_state.total_entries)
c4.metric("My Entries", st.session_state.my_entries)
c5.metric("Eliminated", len(eliminated))

tab_games, tab_picks, tab_sweat, tab_recs, tab_bracket, tab_detail = st.tabs([
    "📋 Games & Spreads", "📊 Pick Tracking", "🔥 Sweat Board",
    "🎯 Recommendations", "🏟️ Bracket", "📐 Methodology"
])

# ═══════════════════════════════════════════════════════════
#  TAB 1: GAMES & SPREADS
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
            live = get_live_info(ta, tb)
            ls = ""
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
    else:
        st.info("No games for this day yet.")

# ═══════════════════════════════════════════════════════════
#  TAB 2: PICK TRACKING
# ═══════════════════════════════════════════════════════════
with tab_picks:
    st.markdown("### 📊 Pick Tracking — Enter Actual Pool Pick Counts")
    st.markdown("Enter the number of entries that picked each team for each day. "
                "This overrides the modeled opponent behavior with **real data**.")

    pick_tab_day = st.selectbox("Day to enter picks for", TOURNAMENT_DAYS,
                                 index=st.session_state.current_day_idx,
                                 format_func=lambda x: f"{x} — {ROUND_NAMES[x]}",
                                 key="pick_tab_day")

    day_games = {gid:g for gid,g in live_bracket.items() if g.get("day")==pick_tab_day}

    if day_games:
        st.markdown("#### Pool Pick Counts")
        for gid, g in sorted(day_games.items(), key=lambda x: x[1].get("time","")):
            ta, tb = g["team_a"], g["team_b"]
            if "W(" in ta or "W(" in tb: continue

            sas = f"({g['seed_a']}) " if g.get("seed_a") else ""
            sbs = f"({g['seed_b']}) " if g.get("seed_b") else ""

            col_a, col_b = st.columns(2)
            with col_a:
                key_a = f"{pick_tab_day}|{ta}"
                cur_a = st.session_state.pick_counts.get(key_a, 0)
                new_a = st.number_input(f"{sas}{ta}", min_value=0,
                    max_value=st.session_state.total_entries,
                    value=cur_a, step=1, key=f"pc_{key_a}")
                st.session_state.pick_counts[key_a] = new_a
            with col_b:
                key_b = f"{pick_tab_day}|{tb}"
                cur_b = st.session_state.pick_counts.get(key_b, 0)
                new_b = st.number_input(f"{sbs}{tb}", min_value=0,
                    max_value=st.session_state.total_entries,
                    value=cur_b, step=1, key=f"pc_{key_b}")
                st.session_state.pick_counts[key_b] = new_b

        # Summary for this day
        st.markdown("---")
        st.markdown("#### Pick Summary")
        total_today = sum(st.session_state.pick_counts.get(f"{pick_tab_day}|{t}", 0) for t in ALL_TEAMS)
        st.metric("Total picks entered for this day", total_today)
        if total_today > 0 and total_today != st.session_state.total_entries:
            st.warning(f"Total picks ({total_today}) doesn't match pool entries ({st.session_state.total_entries}). "
                       "This is fine if not all teams have picks or if some entries were already eliminated.")

        # Show pick distribution
        pick_data = []
        for gid, g in sorted(day_games.items(), key=lambda x: x[1].get("time","")):
            ta, tb = g["team_a"], g["team_b"]
            if "W(" in ta: continue
            cnt_a = st.session_state.pick_counts.get(f"{pick_tab_day}|{ta}", 0)
            cnt_b = st.session_state.pick_counts.get(f"{pick_tab_day}|{tb}", 0)
            tot = max(total_today, 1)
            pick_data.append({"Team": ta, "Seed": g.get("seed_a"), "Picks": cnt_a,
                              "Pick%": f"{cnt_a/tot:.1%}", "Opponent": tb})
            pick_data.append({"Team": tb, "Seed": g.get("seed_b"), "Picks": cnt_b,
                              "Pick%": f"{cnt_b/tot:.1%}", "Opponent": ta})
        if pick_data:
            st.dataframe(pd.DataFrame(pick_data).sort_values("Picks", ascending=False),
                         use_container_width=True, hide_index=True)
    else:
        st.info("No games for this day yet.")

    # ── MY PICKS SECTION ──
    st.markdown("---")
    st.markdown("### 🎯 My Picks — Mark Your Selections")
    st.markdown("Select which team you picked for each entry on each day. "
                "Used teams are automatically tracked and crossed out on future days.")

    for en in range(1, st.session_state.my_entries + 1):
        st.markdown(f"#### Entry #{en}")
        cols = st.columns(min(len(TOURNAMENT_DAYS), 5))
        for i, day in enumerate(TOURNAMENT_DAYS):
            col = cols[i % len(cols)]
            with col:
                pick_key = f"{en}|{day}"
                day_games_for_pick = {gid:g for gid,g in live_bracket.items() if g.get("day")==day}

                # Get available teams for this day (not already used by this entry)
                used_prior = set()
                for prev_day in TOURNAMENT_DAYS:
                    if prev_day == day: break
                    pk = f"{en}|{prev_day}"
                    if pk in st.session_state.my_picks and st.session_state.my_picks[pk]:
                        used_prior.add(st.session_state.my_picks[pk])

                teams_today = []
                for g in day_games_for_pick.values():
                    for t in [g["team_a"], g["team_b"]]:
                        if "W(" not in t and "/" not in t and t not in eliminated:
                            teams_today.append(t)

                options = ["—"] + [t for t in sorted(teams_today) if t not in used_prior]

                # Preserve existing pick even if team was later eliminated
                # (can't un-pick a past day, and the dropdown shouldn't lose your selection)
                current = st.session_state.my_picks.get(pick_key, "—")
                if current and current != "—" and current not in options:
                    options.append(current)
                if current not in options: current = "—"

                sel = st.selectbox(f"{day}", options, index=options.index(current),
                                    key=f"mypick_{pick_key}")
                st.session_state.my_picks[pick_key] = sel if sel != "—" else ""

        # Update used_teams from my_picks
        used = set()
        for day in TOURNAMENT_DAYS:
            pk = f"{en}|{day}"
            if pk in st.session_state.my_picks and st.session_state.my_picks[pk]:
                used.add(st.session_state.my_picks[pk])
        st.session_state.used_teams[en] = used

    # ── TEAM AVAILABILITY TRACKER ──
    st.markdown("---")
    st.markdown("### 📈 Entries Still Available Per Team")
    st.markdown("Based on actual pick data entered above, how many pool entries still have each team available?")

    avail_day = st.selectbox("Check availability as of", TOURNAMENT_DAYS,
                              index=st.session_state.current_day_idx,
                              format_func=lambda x: f"{x} — {ROUND_NAMES[x]}",
                              key="avail_day")
    avail_idx = TOURNAMENT_DAYS.index(avail_day)

    avail_rows = []
    for team in ALL_TEAMS:
        if team in eliminated: continue
        seed = get_team_seed(team)
        total_used = 0
        for d_i in range(avail_idx):
            d = TOURNAMENT_DAYS[d_i]
            total_used += st.session_state.pick_counts.get(f"{d}|{team}", 0)
        remaining = max(st.session_state.total_entries - total_used, 0)
        pct_avail = remaining / max(st.session_state.total_entries, 1)
        avail_rows.append({"Team": team, "Seed": seed, "Times Picked": total_used,
                           "Entries Still Have": remaining,
                           "% Available": f"{pct_avail:.1%}"})

    if avail_rows:
        df_avail = pd.DataFrame(avail_rows).sort_values("Times Picked", ascending=False)
        st.dataframe(df_avail, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════
#  TAB 3: SWEAT BOARD
# ═══════════════════════════════════════════════════════════
with tab_sweat:
    st.markdown("### 🔥 Sweat Board — Live Scores + Pick %")
    st.markdown("Your picks are **highlighted in green**. Eliminated teams are crossed out.")

    sweat_day = st.selectbox("Day", TOURNAMENT_DAYS, index=st.session_state.current_day_idx,
                              format_func=lambda x: f"{x} — {ROUND_NAMES[x]}",
                              key="sweat_day")

    # Collect my picks for this day
    my_picks_today = {}
    for en in range(1, st.session_state.my_entries + 1):
        pk = f"{en}|{sweat_day}"
        pick = st.session_state.my_picks.get(pk, "")
        if pick: my_picks_today[en] = pick

    if my_picks_today:
        st.markdown("**My picks today:** " + " | ".join(
            [f"Entry #{en}: **{pick}**" for en, pick in my_picks_today.items()]))
    else:
        st.caption("No picks entered for this day yet. Go to Pick Tracking tab to set them.")

    st.markdown("---")
    day_games = {gid:g for gid,g in live_bracket.items() if g.get("day")==sweat_day}

    total_picks_day = sum(
        st.session_state.pick_counts.get(f"{sweat_day}|{t}", 0)
        for g in day_games.values()
        for t in [g["team_a"], g["team_b"]]
        if "W(" not in t
    )

    if day_games:
        for gid, g in sorted(day_games.items(), key=lambda x: x[1].get("time","")):
            ta, tb = g["team_a"], g["team_b"]
            if "W(" in ta: continue

            sas = f"({g['seed_a']})" if g.get("seed_a") else ""
            sbs = f"({g['seed_b']})" if g.get("seed_b") else ""

            # Pick counts
            cnt_a = st.session_state.pick_counts.get(f"{sweat_day}|{ta}", 0)
            cnt_b = st.session_state.pick_counts.get(f"{sweat_day}|{tb}", 0)
            pct_a = f"{cnt_a/max(total_picks_day,1):.1%}" if total_picks_day > 0 else "—"
            pct_b = f"{cnt_b/max(total_picks_day,1):.1%}" if total_picks_day > 0 else "—"

            # Is this my pick?
            my_pick_entries_a = [en for en, pk in my_picks_today.items() if pk == ta]
            my_pick_entries_b = [en for en, pk in my_picks_today.items() if pk == tb]
            is_mine_a = len(my_pick_entries_a) > 0
            is_mine_b = len(my_pick_entries_b) > 0

            # Status
            live = get_live_info(ta, tb)
            score_a = score_b = "—"
            status_text = "🔜 Upcoming"
            if live:
                score_a = str(live["score_a"]); score_b = str(live["score_b"])
                if live["is_live"]: status_text = f"🔴 {live['detail']}"
                elif live["is_final"]: status_text = "✅ FINAL"

            is_elim_a = ta in eliminated
            is_elim_b = tb in eliminated
            won_a = gid in all_winners and all_winners[gid] == ta
            won_b = gid in all_winners and all_winners[gid] == tb

            # Build styled HTML for each team
            def team_html(team, seed_str, cnt, pct, is_mine, is_elim, won, score, entries_list):
                bg = ""
                if is_mine and won:
                    bg = "background: linear-gradient(90deg, #27ae60 0%, #2ecc71 100%); color: white;"
                elif is_mine and is_elim:
                    bg = "background: linear-gradient(90deg, #c0392b 0%, #e74c3c 100%); color: white;"
                elif is_mine:
                    bg = "background: linear-gradient(90deg, #2980b9 0%, #3498db 100%); color: white;"

                text_decor = "text-decoration: line-through; opacity: 0.5;" if is_elim else ""
                icon = "🏆" if won else ("❌" if is_elim else "")
                mine_badge = ""
                if is_mine:
                    entry_nums = ", ".join([f"#{e}" for e in entries_list])
                    mine_badge = f'<span style="background:#f39c12;color:white;padding:1px 6px;border-radius:10px;font-size:10px;margin-left:4px">MY PICK {entry_nums}</span>'

                return f'''<div style="padding:8px 12px;border-radius:6px;margin:2px 0;{bg}">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-weight:bold;font-size:16px;{text_decor}">{icon} {seed_str} {team}{mine_badge}</span>
                        <span style="font-size:20px;font-weight:bold">{score}</span>
                    </div>
                    <div style="font-size:12px;opacity:0.8">Picks: {cnt} ({pct})</div>
                </div>'''

            html = f'''<div style="border:1px solid #333;border-radius:8px;padding:8px;margin-bottom:12px;">
                <div style="text-align:center;font-size:11px;color:#888;margin-bottom:4px">{g.get("time","TBD")} · {g.get("loc","TBD")} · {status_text}</div>
                {team_html(ta, sas, cnt_a, pct_a, is_mine_a, is_elim_a, won_a, score_a, my_pick_entries_a)}
                {team_html(tb, sbs, cnt_b, pct_b, is_mine_b, is_elim_b, won_b, score_b, my_pick_entries_b)}
            </div>'''
            st.markdown(html, unsafe_allow_html=True)
    else:
        st.info("No games for this day yet.")

    # Survival summary
    st.markdown("---")
    st.markdown("### 📊 Entry Survival Status")
    for en in range(1, st.session_state.my_entries + 1):
        alive = True
        picks_made = []
        for day in TOURNAMENT_DAYS:
            pk = f"{en}|{day}"
            pick = st.session_state.my_picks.get(pk, "")
            if pick:
                won = pick not in eliminated
                lost = pick in eliminated
                status = "✅" if won else "❌"
                picks_made.append(f"{status} {day}: {pick}")
                if lost: alive = False

        status_icon = "🟢 ALIVE" if alive else "🔴 ELIMINATED"
        st.markdown(f"**Entry #{en} — {status_icon}**")
        if picks_made:
            st.caption(" | ".join(picks_made))
        else:
            st.caption("No picks made yet")


# ═══════════════════════════════════════════════════════════
#  TAB 4: RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════
with tab_recs:
    st.markdown("### 🎯 Pick Recommendations")
    st.markdown("Two picks per entry: **🛡️ Safety** (survive today, preserve future assets) "
                "and **⚡ Leverage** (maximum contrarian edge while staying +EV)")

    tg = {gid:g for gid,g in live_bracket.items() if g.get("day")==current_day}
    if tg:
        at = []
        for gid, g in tg.items():
            ok=f"spread_{gid}"; sp=st.session_state.spread_overrides.get(ok, g.get("spread") or 0)
            wp_=win_prob(sp)
            if g["team_a"] not in eliminated and "W(" not in g["team_a"]:
                at.append({"team":g["team_a"],"seed":g.get("seed_a"),"win_prob":wp_,
                           "opponent":g["team_b"],"spread":sp,"region":g["region"]})
            if g["team_b"] not in eliminated and "W(" not in g["team_b"]:
                at.append({"team":g["team_b"],"seed":g.get("seed_b"),"win_prob":1-wp_,
                           "opponent":g["team_a"],"spread":-sp,"region":g["region"]})

        opp = compute_opp_pct_model(at, st.session_state.current_day_idx, len(TOURNAMENT_DAYS),
                                     st.session_state.pick_counts, current_day,
                                     st.session_state.total_entries)

        has_actual = any(st.session_state.pick_counts.get(f"{current_day}|{t['team']}", 0) > 0 for t in at)
        if has_actual:
            st.success("✅ Using **actual pick data** for opponent modeling")
        else:
            st.info("📊 Using **modeled opponent behavior** (enter actual picks in Pick Tracking tab for better accuracy)")

        # Build future days with SEED DATA (critical for smart future play)
        fdt = []
        for fi in range(st.session_state.current_day_idx+1, min(st.session_state.current_day_idx+5, len(TOURNAMENT_DAYS))):
            fd=TOURNAMENT_DAYS[fi]; fg={gid:g for gid,g in live_bracket.items() if g.get("day")==fd}
            fa=[]
            for gid,g in fg.items():
                ok=f"spread_{gid}"; sp=st.session_state.spread_overrides.get(ok,g.get("spread") or 0); wp_=win_prob(sp)
                if g["team_a"] not in eliminated and "W(" not in g["team_a"]:
                    fa.append({"team":g["team_a"],"win_prob":wp_,"seed":g.get("seed_a")})
                if g["team_b"] not in eliminated and "W(" not in g["team_b"]:
                    fa.append({"team":g["team_b"],"win_prob":1-wp_,"seed":g.get("seed_b")})
            fdt.append(fa)

        if st.button("🚀 Run Simulation Engine", type="primary", use_container_width=True):
            prog = st.progress(0, "Running...")
            ar = {}
            for en in range(1, st.session_state.my_entries+1):
                used = st.session_state.used_teams.get(en, set())
                ea = [t for t in at if t["team"] not in used]
                res = []
                for idx, ti in enumerate(ea):
                    pv = ((en-1)*len(ea)+idx)/max(st.session_state.my_entries*len(ea),1)
                    prog.progress(min(pv,1.0), f"Entry #{en}: {ti['team']}...")

                    sv = sim_survivor(ti["team"], ea, fdt, st.session_state.n_sims,
                                       st.session_state.current_day_idx, len(TOURNAMENT_DAYS), used,
                                       st.session_state.pick_counts, st.session_state.total_entries)
                    op = opp.get(ti["team"], 0)
                    fv = compute_future_value(ti["seed"], ti["win_prob"],
                                              st.session_state.current_day_idx, len(TOURNAMENT_DAYS))
                    avail_count = compute_entries_with_team_available(
                        ti["team"], st.session_state.current_day_idx,
                        st.session_state.pick_counts, st.session_state.total_entries)

                    safety = compute_safety_score(ti["win_prob"], fv, sv)
                    lev = compute_leverage_score(ti["win_prob"], op, fv, sv)

                    res.append({"Team":ti["team"],"Seed":ti["seed"],"Region":ti["region"],
                        "Opponent":ti["opponent"],"Spread":ti["spread"],"Win%":ti["win_prob"],
                        "Opp Pick%":op,"Future Value":fv,"Entries Avail":avail_count,
                        "Survival":sv,"Safety":safety,"Leverage":lev})
                ar[en] = res
            prog.progress(1.0, "Done!"); st.session_state.sim_results = ar; time.sleep(0.3); prog.empty()

        if st.session_state.sim_results:
            for en, res in st.session_state.sim_results.items():
                st.markdown(f"#### Entry #{en}")
                used = st.session_state.used_teams.get(en, set())
                if used:
                    used_display = []
                    for t in sorted(used):
                        used_display.append(f"~~{t}~~" if t in eliminated else t)
                    st.caption(f"Already used: {', '.join(used_display)}")
                if not res: st.warning("No teams available."); continue

                # Safety pick: highest safety score above win% threshold
                safety_picks = [r for r in res if r["Win%"] >= MIN_WP_SAFETY]
                safety_picks.sort(key=lambda x: x["Safety"], reverse=True)

                # Leverage pick: highest leverage score above win% threshold
                lev_picks = [r for r in res if r["Win%"] >= MIN_WP_LEVERAGE]
                lev_picks.sort(key=lambda x: x["Leverage"], reverse=True)

                col_s, col_l = st.columns(2)
                with col_s:
                    if safety_picks:
                        top_s = safety_picks[0]
                        st.markdown(f"""<div style="border:2px solid #2ecc71;border-radius:8px;padding:12px;background:rgba(46,204,113,0.1)">
                            <div style="font-size:13px;color:#2ecc71;font-weight:bold">🛡️ SAFETY PICK</div>
                            <div style="font-size:20px;font-weight:bold">({top_s['Seed']}) {top_s['Team']}</div>
                            <div style="font-size:13px">vs {top_s['Opponent']} · Spread: {top_s['Spread']:+.1f}</div>
                            <div style="font-size:12px;margin-top:6px">
                                Win: {top_s['Win%']:.0%} · Opp: {top_s['Opp Pick%']:.0%} · FV: {top_s['Future Value']:.2f} · Surv: {top_s['Survival']:.0%}<br>
                                <b>Safety Score: {top_s['Safety']:.3f}</b>
                            </div>
                        </div>""", unsafe_allow_html=True)
                    else:
                        st.warning("No picks above safety threshold")

                with col_l:
                    if lev_picks:
                        top_l = lev_picks[0]
                        st.markdown(f"""<div style="border:2px solid #f39c12;border-radius:8px;padding:12px;background:rgba(243,156,18,0.1)">
                            <div style="font-size:13px;color:#f39c12;font-weight:bold">⚡ LEVERAGE PICK</div>
                            <div style="font-size:20px;font-weight:bold">({top_l['Seed']}) {top_l['Team']}</div>
                            <div style="font-size:13px">vs {top_l['Opponent']} · Spread: {top_l['Spread']:+.1f}</div>
                            <div style="font-size:12px;margin-top:6px">
                                Win: {top_l['Win%']:.0%} · Opp: {top_l['Opp Pick%']:.0%} · FV: {top_l['Future Value']:.2f} · Surv: {top_l['Survival']:.0%}<br>
                                <b>Leverage Score: {top_l['Leverage']:.3f}</b>
                            </div>
                        </div>""", unsafe_allow_html=True)
                    else:
                        st.warning("No picks above leverage threshold")

                # If they're the same pick, note it
                if safety_picks and lev_picks and safety_picks[0]["Team"] == lev_picks[0]["Team"]:
                    st.info(f"🎯 Both scores point to **{safety_picks[0]['Team']}** — strong pick across the board.")

                # Full table sorted by safety
                st.markdown("##### Full Rankings")
                sort_col = st.radio("Sort by", ["Safety", "Leverage", "Win%", "Future Value"],
                                     horizontal=True, key=f"sort_{en}")
                df = pd.DataFrame(res)
                df = df.sort_values(sort_col, ascending=(sort_col == "Future Value"))

                for col,fmt in [("Win%","{:.1%}"),("Opp Pick%","{:.1%}"),("Future Value","{:.2f}"),
                                ("Survival","{:.1%}"),("Safety","{:.3f}"),("Leverage","{:.3f}"),
                                ("Spread","{:+.1f}")]:
                    df[col] = df[col].apply(lambda x, f=fmt: f.format(x))
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.markdown("---")

            st.markdown("""### 📝 How to Read This

**🛡️ Safety Pick** — Best team to survive today without wasting a premium asset.
The formula heavily penalizes burning 1/2-seeds in early rounds because you'll need them
when the field narrows. A 6-seed at 72% often scores higher than a 1-seed at 99% early on.

**⚡ Leverage Pick** — Best contrarian play that's still +EV. Maximizes opponent eliminations.
If 15% of the pool is on Team X and only 3% on Team Y, and both have ~70% win probability,
Team Y is the leverage play — when it wins, you survive while more opponents are eliminated.

**Key columns:**
- **Future Value** — 0.0 to 1.0, how valuable it is to SAVE this team. High FV = don't use today.
  1-seeds in Round 1 have ~0.95 FV. 8-seeds have ~0.0. This drops as the tournament progresses.
- **Survival** — Monte Carlo probability of surviving ALL remaining rounds if you pick this team today.
  The sim uses smart future play (saves top seeds) instead of always grabbing the best available.
- **Opp Pick%** — What % of opponents are on this team. Lower = more contrarian.
- **Entries Avail** — How many opponents still have this team available (based on actual pick data).

**When to pick Safety vs Leverage:**
- **Ahead / many entries alive** → Leverage (maximize opponent eliminations)
- **Behind / need to survive** → Safety (don't die today)
- **Both agree** → Strong signal, take it""")
        else:
            st.info("Click **Run Simulation Engine** to generate picks.")
    else:
        st.info("No games for this day yet.")


# ═══════════════════════════════════════════════════════════
#  TAB 5: BRACKET
# ═══════════════════════════════════════════════════════════
with tab_bracket:
    st.markdown("### 🏟️ Live Bracket")
    rl = {"R1":"Round of 64","R2":"Round of 32","S16":"Sweet 16",
          "E8":"Elite 8","FF":"Final Four","CHAMP":"Championship"}
    for rnd in ["R1","R2","S16","E8","FF","CHAMP"]:
        rg = {gid:g for gid,g in live_bracket.items() if get_round(gid)==rnd}
        if not rg: continue
        st.markdown(f"#### {rl[rnd]}")
        rows = []
        for gid,g in sorted(rg.items()):
            ta,tb = g["team_a"],g["team_b"]
            sa="❌" if ta in eliminated else ("🏆" if gid in all_winners and all_winners[gid]==ta else "✅")
            sb_="❌" if tb in eliminated else ("🏆" if gid in all_winners and all_winners[gid]==tb else "✅")
            sp=st.session_state.spread_overrides.get(f"spread_{gid}",g.get("spread"))
            sps=f"{sp:+.1f}" if sp is not None else "TBD"
            rows.append({"Day":g.get("day","TBD"),"Region":g.get("region",""),
                "Team A":f"{sa} ({g['seed_a']}) {ta}" if g.get("seed_a") else f"{sa} {ta}",
                "Team B":f"{sb_} ({g['seed_b']}) {tb}" if g.get("seed_b") else f"{sb_} {tb}",
                "Spread":sps,"Winner":all_winners.get(gid,"—"),
                "Status":"✅" if gid in all_winners else ("⏳" if not g.get("teams_known",True) else "🔜")})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.markdown("---")
    st.markdown(f"**{len(eliminated)} eliminated:** {', '.join(sorted(eliminated)) if eliminated else 'None yet'}")


# ═══════════════════════════════════════════════════════════
#  TAB 6: METHODOLOGY
# ═══════════════════════════════════════════════════════════
with tab_detail:
    st.markdown("""### 📐 Methodology

#### Auto-Update Pipeline
ESPN Scoreboard API → match teams → propagate winners through bracket tree → generate future matchups

#### Pick Data Integration
When you enter actual pool pick counts in the **Pick Tracking** tab:
1. **Opponent Pick %** switches from modeled → actual data for that day
2. **Entries Available** computed by subtracting cumulative picks from total pool size
3. Future days still use the seed-saving model until you enter real data for those days

#### Entries Available Per Team
For each team, we track how many pool entries have already used that team:
`Entries Available = Total Pool Entries - Sum(picks on this team across all prior days)`

This tells you how many opponents can still pick this team in future rounds.

#### Win Probability
Spread → win% via normal CDF (σ = 11.0)""")
    st.dataframe(pd.DataFrame([{"Spread":f"{s:+.1f}","Win%":f"{win_prob(s):.1%}"}
        for s in [-1.5,-3.5,-6.5,-10.5,-16.5,-22.5,-27.5]]), hide_index=True)
    st.markdown("""
#### Opponent Model (Hybrid)
- **With actual data**: Pick% = team's actual picks / total picks that day
- **Without actual data**: win_prob^1.5 × seed-save discount × brand boost

#### Future Value (NEW in v4)
Each team gets a Future Value score (0.0 to 1.0) representing how valuable it is to SAVE them:
- **Seed premium**: 1-seeds = 0.95, 2-seeds = 0.82, 3-seeds = 0.60, 4 = 0.40, 5 = 0.25, 6-7 = 0.10, 8+ = 0.0
- **Time scaling**: scales with rounds remaining (more future = more valuable to save)
- **Alive factor**: weighted by win probability (team must actually survive to have future value)

#### Smart Future Simulation (NEW in v4)
The Monte Carlo sim now uses **smart future play** instead of greedy:
- Early tournament (>3 rounds left): avoids 1-seeds AND 2-seeds in future picks
- Mid tournament (2-3 rounds left): avoids 1-seeds only
- Late tournament (last round): uses whatever is best
This properly models the COST of burning a premium team early.

#### Safety Score
`win_prob × (1 - 0.7 × future_value) × (0.3 + 0.7 × survival)`
Maximizes today's survival while heavily penalizing use of future-valuable teams.

#### Leverage Score
`(1 - opp_pct)^0.6 × win_prob × (1 - 0.5 × future_value) × survival^0.5`
Maximizes contrarian edge (sub-linear to avoid chasing extreme low-pick teams) with moderate future-value penalty.

#### Minimum Win Probability Thresholds
- Safety picks: must be ≥55% win probability
- Leverage picks: must be ≥50% win probability

#### Data Persistence
- All picks, spreads, settings, and pick counts **auto-save** to `survivor_state.json` on every interaction
- On app restart, data **auto-loads** from this file
- Use **Export/Import** in sidebar for Streamlit Cloud portability""")

st.markdown("---")
st.caption("Survivor Engine v4.0 | Smart sim + Future Value + Safety/Leverage picks | ESPN auto-update")

# ═══════════════════════════════════════════════════════════
#  AUTO-SAVE — runs at end of every Streamlit rerun
# ═══════════════════════════════════════════════════════════
save_state()
