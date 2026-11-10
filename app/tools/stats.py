from typing import Optional

import pandas as pd

from app.db import q
from app.resolve import resolve_player, resolve_team


def _i(x):
    """NaN/None-safe int (SQL SUM over zero rows gives NULL -> NaN)."""
    return 0 if x is None or pd.isna(x) else int(x)


def _phase_clause(phase: Optional[str]):
    if phase in ("powerplay", "middle", "death"):
        return " AND d.phase = ?", [phase]
    return "", []


def player_batting_stats(player: str, phase: Optional[str] = None,
                        venue: Optional[str] = None, season: Optional[str] = None) -> dict:
    """Batting stats for a player, optionally filtered by phase, venue, season."""
    p = resolve_player(player)
    if not p:
        return {"error": f"Player '{player}' not found"}
    sql = """
        SELECT SUM(d.runs_batter) AS runs,
            COUNT(*) FILTER (WHERE d.is_legal_for_batter) AS balls,
            COUNT(*) FILTER (WHERE d.player_out = d.batter AND d.is_wicket
                                AND d.wicket_kind NOT IN ('retired hurt', 'retired out')) AS dismissals,
             COUNT(*) FILTER (WHERE d.runs_batter = 4) AS fours,
             COUNT(*) FILTER (WHERE d.runs_batter = 6) AS sixes,
             COUNT(DISTINCT d.match_id) AS matches
      FROM deliveries d JOIN matches m USING (match_id)
      WHERE d.batter = ?"""
    params = [p]
    clause, extra = _phase_clause(phase)
    sql += clause
    params += extra
    if venue:
        sql += " AND m.venue ILIKE ?"
        params.append(f"%{venue}%")
    if season:
        sql += " AND m.season = ?"
        params.append(season)
    r = q(sql, params).iloc[0]
    if _i(r.matches) == 0:
        return {"error": f"No data for {p} with these filters "
                         f"(phase={phase}, venue={venue}, season={season})"}
    runs, balls, outs = _i(r.runs), _i(r.balls), _i(r.dismissals)
    return {
        "player": p, "phase": phase, "venue": venue, "season": season,
        "matches": _i(r.matches), "runs": runs, "balls": balls,
        "average": round(runs / outs, 2) if outs else None,
        "strike_rate": round(runs * 100 / balls, 2) if balls else None,
        "fours": _i(r.fours), "sixes": _i(r.sixes),
    }


def player_bowling_stats(player: str, phase: Optional[str] = None,
                        venue: Optional[str] = None, season: Optional[str] = None) -> dict:
    """Bowling stats for a player, optionally filtered by phase, venue, season."""
    p = resolve_player(player)
    if not p:
        return {"error": f"Player '{player}' not found"}
    sql = """
        SELECT SUM(d.runs_batter + COALESCE(CASE WHEN d.is_wide OR d.is_noball
                                        THEN d.runs_extras END, 0)) AS runs_conceded,
            COUNT(*) FILTER (WHERE NOT d.is_wide AND NOT d.is_noball) AS legal_balls,
            COUNT(*) FILTER (WHERE d.bowler_wicket) AS wickets,
            COUNT(DISTINCT d.match_id) AS matches
        FROM deliveries d JOIN matches m USING (match_id)
        WHERE d.bowler = ?"""
    params = [p]
    clause, extra = _phase_clause(phase)
    sql += clause
    params += extra
    if venue:
        sql += " AND m.venue ILIKE ?"
        params.append(f"%{venue}%")
    if season:
        sql += " AND m.season = ?"
        params.append(season)
    r = q(sql, params).iloc[0]
    if _i(r.matches) == 0:
        return {"error": f"No data for {p} with these filters "
                         f"(phase={phase}, venue={venue}, season={season})"}
    runs, balls, wk = _i(r.runs_conceded), _i(r.legal_balls), _i(r.wickets)
    return {
        "player": p, "phase": phase, "venue": venue, "season": season,
        "matches": _i(r.matches), "wickets": wk, "legal_balls": balls,
        "runs_conceded": runs,
        "economy": round(runs * 6 / balls, 2) if balls else None,
        "bowling_average": round(runs / wk, 2) if wk else None,
    }


def head_to_head(batter: str, bowler: str) -> dict:
    """Career record of one batter against one bowler."""
    b, w = resolve_player(batter), resolve_player(bowler)
    if not b or not w:
        return {"error": "Could not resolve one of the players"}
    r = q("""
        SELECT SUM(runs_batter) runs,
            COUNT(*) FILTER (WHERE is_legal_for_batter) balls,
            COUNT(*) FILTER (WHERE bowler_wicket AND player_out = batter) outs
        FROM deliveries WHERE batter = ? AND bowler = ?""", [b, w]).iloc[0]
    runs, balls = _i(r.runs), _i(r.balls)
    if balls == 0:
        return {"error": f"{b} and {w} have no recorded deliveries against each other"}
    return {"batter": b, "bowler": w, "runs": runs, "balls": balls,
            "dismissals": _i(r.outs),
            "strike_rate": round(runs * 100 / balls, 2)}


def team_form(team: str, last_n: int = 5) -> dict:
    """Last N results of a team as a W/L string."""
    t = resolve_team(team)
    if not t:
        return {"error": f"Team '{team}' not found"}
    df = q("""SELECT date, team1, team2, winner FROM matches
                WHERE team1 = ? OR team2 = ? ORDER BY date DESC LIMIT ?""", [t, t, last_n])
    results = ["W" if w == t else "L" if w else "NR" for w in df["winner"]]
    return {"team": t, "last_n": last_n, "form": "".join(results),
            "matches": df.to_dict("records")}


def venue_stats(venue: str) -> dict:
    """Number of matches and average first-innings score at a venue."""
    r = q("""
        SELECT COUNT(DISTINCT m.match_id) matches,
                ROUND(AVG(inn.total), 1) avg_first_innings
        FROM matches m JOIN (
            SELECT match_id, SUM(runs_total) total FROM deliveries
            WHERE innings = 1 GROUP BY match_id) inn USING (match_id)
        WHERE m.venue ILIKE ?""", [f"%{venue}%"]).iloc[0]
    if _i(r.matches) == 0:
        return {"error": f"No matches found at a venue matching '{venue}'"}
    return {"venue": venue, "matches": _i(r.matches),
            "avg_first_innings_score": float(r.avg_first_innings)}