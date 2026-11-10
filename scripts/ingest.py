import json, glob, os
import pandas as pd
import duckdb

RAW = "data/raw/ipl/*.json"
OUT = "data/processed"
os.makedirs(OUT, exist_ok=True)

matches, deliveries = [], []

for path in glob.glob(RAW):
    match_id = os.path.basename(path).replace(".json", "")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    info = d["info"]
    matches.append({
        "match_id": match_id,
        "date": info["dates"][0],
        "season": str(info.get("season")),
        "venue": info.get("venue"),
        "city": info.get("city"),
        "team1": info["teams"][0],
        "team2": info["teams"][1],
        "winner": info.get("outcome", {}).get("winner"),
        "toss_winner": info["toss"]["winner"],
        "toss_decision": info["toss"]["decision"],
        "player_of_match": (info.get("player_of_match") or [None])[0],
    })
    for inn_no, inning in enumerate(d["innings"], start=1):
        if inning.get("super_over"):
            continue
        team = inning["team"]
        for over in inning["overs"]:
            for ball_no, de in enumerate(over["deliveries"], start=1):
                wk = de.get("wickets", [])
                deliveries.append({
                    "match_id": match_id,
                    "innings": inn_no,
                    "batting_team": team,
                    "over": over["over"],
                    "ball": ball_no,
                    "batter": de["batter"],
                    "bowler": de["bowler"],
                    "non_striker": de["non_striker"],
                    "runs_batter": de["runs"]["batter"],
                    "runs_extras": de["runs"]["extras"],
                    "runs_total": de["runs"]["total"],
                    "is_wide": "wides" in de.get("extras", {}),
                    "is_noball": "noballs" in de.get("extras", {}),
                    "is_wicket": len(wk) > 0,
                    "wicket_kind": wk[0]["kind"] if wk else None,
                    "player_out": wk[0]["player_out"] if wk else None,
                })

m = pd.DataFrame(matches)
dl = pd.DataFrame(deliveries)

TEAM_MAP = {
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "Delhi Daredevils": "Delhi Capitals",
    "Kings XI Punjab": "Punjab Kings",
    "Rising Pune Supergiants": "Rising Pune Supergiant",
}
for col in ["team1", "team2", "winner", "toss_winner"]:
    m[col] = m[col].replace(TEAM_MAP)
dl["batting_team"] = dl["batting_team"].replace(TEAM_MAP)

# Derived columns
dl["phase"] = pd.cut(dl["over"], bins=[-1, 5, 14, 19],
                    labels=["powerplay", "middle", "death"]).astype(str)
# Legal ball for batter = not a wide
dl["is_legal_for_batter"] = ~dl["is_wide"]
# Bowler wicket credit excludes run outs etc.
dl["bowler_wicket"] = dl["is_wicket"] & ~dl["wicket_kind"].isin(
    ["run out", "retired hurt", "retired out", "obstructing the field"])

m.to_parquet(f"{OUT}/matches.parquet", index=False)
dl.to_parquet(f"{OUT}/deliveries.parquet", index=False)
print(len(m), "matches,", len(dl), "deliveries")