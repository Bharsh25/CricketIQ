import re
from app.db import q

FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|copy|pragma|export)\b", re.I)
ALLOWED_TABLES = {"matches", "deliveries"}

def run_sql(query: str, limit: int = 50) -> dict:
    """Run a read-only SELECT over tables matches and deliveries."""
    s = query.strip().rstrip(";")
    if not s.lower().startswith(("select", "with")):
        return {"error": "Only SELECT queries are allowed"}
    if FORBIDDEN.search(s) or ";" in s:
        return {"error": "Query contains forbidden keywords"}
    tables = set(re.findall(r"(?:from|join)\s+([a-zA-Z_]+)", s, re.I))
    if not tables.issubset(ALLOWED_TABLES):
        return {"error": f"Only tables {sorted(ALLOWED_TABLES)} are allowed"}
    try:
        df = q(f"SELECT * FROM ({s}) LIMIT {int(limit)}")
        return {"columns": list(df.columns), "rows": df.to_dict("records")}
    except Exception as e:
        return {"error": str(e)[:300]}

SCHEMA_HINT = """
matches(match_id, date, season, venue, city, team1, team2, winner, toss_winner,
        toss_decision, player_of_match)
deliveries(match_id, innings, batting_team, over, ball, batter, bowler, non_striker,
            runs_batter, runs_extras, runs_total, is_wide, is_noball, is_wicket,
            wicket_kind, player_out, phase, is_legal_for_batter, bowler_wicket)
Rules:
- Wickets taken BY A BOWLER: count rows WHERE bowler_wicket = TRUE.
    Never use is_wicket for this: it includes run outs, which are not the bowler's.
- Runs scored by a batter: SUM(runs_batter). Balls faced: rows WHERE is_legal_for_batter.
- phase: 'powerplay' (over 0-5), 'middle' (6-14), 'death' (15-19). over is 0-19.
- Player names use Cricsheet format, e.g. 'B Kumar' = Bhuvneshwar Kumar, 'YS Chahal'.
"""