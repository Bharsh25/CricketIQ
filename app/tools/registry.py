from langchain_core.tools import tool
from typing import Optional
from app.tools import stats
from app.tools.sql_tool import run_sql, SCHEMA_HINT
from app.tools.rag import search_cricket_docs

@tool
def batting_stats(player: str, phase: Optional[str] = None,
                    venue: Optional[str] = None, season: Optional[str] = None) -> dict:
    """Batting stats (runs, average, strike rate, boundaries). phase: powerplay|middle|death."""
    return stats.player_batting_stats(player, phase, venue, season)

@tool
def bowling_stats(player: str, phase: Optional[str] = None,
                    venue: Optional[str] = None, season: Optional[str] = None) -> dict:
    """Bowling stats (wickets, economy, average). phase: powerplay|middle|death."""
    return stats.player_bowling_stats(player, phase, venue, season)

@tool
def batter_vs_bowler(batter: str, bowler: str) -> dict:
    """Head-to-head record of a batter against a bowler."""
    return stats.head_to_head(batter, bowler)

@tool
def team_recent_form(team: str, last_n: int = 5) -> dict:
    """Last N results of a team as a W/L string."""
    return stats.team_form(team, last_n)

@tool
def venue_info(venue: str) -> dict:
    """Average first innings score and number of matches at a venue."""
    return stats.venue_stats(venue)

@tool(description=(
    "LAST RESORT. Use only for leaderboards and custom aggregations (most, highest, top N). "
    "Never use it for one player's batting or bowling stats, batter-vs-bowler records, "
    "team form or venue stats: dedicated tools exist for those.\nSchema: " + SCHEMA_HINT))
def sql_query(query: str) -> dict:
    return run_sql(query)

@tool
def cricket_knowledge(query: str) -> dict:
    """Look up cricket rules, definitions and past match narratives.
NEVER use this for player statistics, use batting_stats or bowling_stats."""
    return search_cricket_docs(query)

TOOLS = [
    batting_stats,
    bowling_stats,
    batter_vs_bowler,
    team_recent_form,
    venue_info,
    sql_query,
    cricket_knowledge
]