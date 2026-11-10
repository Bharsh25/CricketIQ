from app.tools.stats import player_batting_stats, head_to_head

def test_kohli_runs_positive():
    r = player_batting_stats("Virat Kohli")
    assert r["runs"] > 5000

def test_unknown_player():
    assert "error" in player_batting_stats("zzzzzz")

def test_phase_filter_reduces_balls():
    all_ = player_batting_stats("Kohli")["balls"]
    pp = player_batting_stats("Kohli", phase="powerplay")["balls"]
    assert pp < all_