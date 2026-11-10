from rapidfuzz import process, fuzz
from app.db import q

_players, _pop, _teams = None, {}, None

TEAM_ALIASES = {
    "rcb": "Royal Challengers Bengaluru", "mi": "Mumbai Indians",
    "csk": "Chennai Super Kings", "kkr": "Kolkata Knight Riders",
    "srh": "Sunrisers Hyderabad", "dc": "Delhi Capitals",
    "rr": "Rajasthan Royals", "pbks": "Punjab Kings",
    "lsg": "Lucknow Super Giants", "gt": "Gujarat Titans",
}

# Optional hand-checked shortcuts for first-name-only queries
PLAYER_ALIASES = {
    "rohit": "RG Sharma", "virat": "V Kohli", "dhoni": "MS Dhoni",
    "surya": "SA Yadav", "hardik": "HH Pandya",
}


def _load():
    global _players, _pop, _teams
    if _players is None:
        df = q("""SELECT n, SUM(c) AS c FROM (
                    SELECT batter AS n, COUNT(*) AS c FROM deliveries GROUP BY 1
                    UNION ALL
                    SELECT bowler, COUNT(*) FROM deliveries GROUP BY 1)
                    GROUP BY n ORDER BY c DESC, n""")
        _players = df["n"].tolist()
        _pop = dict(zip(df["n"], df["c"]))
        _teams = q("""SELECT DISTINCT n FROM (SELECT team1 n FROM matches
                        UNION SELECT team2 FROM matches) ORDER BY 1""")["n"].tolist()


def resolve_player(name: str, cutoff=70):
    _load()
    raw = name.strip()
    if not raw:
        return None
    if raw in _pop:                                   # exact match
        return raw
    low = raw.lower()
    alias = PLAYER_ALIASES.get(low)
    if alias and alias in _pop:
        return alias

    tokens = raw.replace(".", " ").split()
    surname = tokens[-1].lower()
    initial = tokens[0][0].lower() if len(tokens) > 1 else None

    # same surname (+ same first initial when a first name was given)
    cands = [p for p in _players
            if p.split()[-1].lower() == surname
            and (initial is None or p[0].lower() == initial)]
    if cands:
        return max(cands, key=lambda n: _pop[n])      # most-played wins

    # fallback: fuzzy match
    hits = process.extract(raw, _players, scorer=fuzz.WRatio,
                            score_cutoff=cutoff, limit=5)
    if not hits:
        return None
    top = hits[0][1]
    close = [h[0] for h in hits if h[1] >= top - 2]
    return max(close, key=lambda n: _pop[n])


def resolve_team(name: str, cutoff=70):
    _load()
    key = name.strip().lower()
    if key in TEAM_ALIASES:
        return TEAM_ALIASES[key]
    hit = process.extractOne(name, _teams, scorer=fuzz.WRatio, score_cutoff=cutoff)
    return hit[0] if hit else None