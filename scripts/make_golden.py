import json
from app.tools.stats import (player_batting_stats as bat,
                            player_bowling_stats as bowl, head_to_head as h2h)

cases = []

def add(q, tool, value):
    if value is not None:
        cases.append({"q": q, "tool": tool, "expected": value})

batters = ["Kohli", "Rohit Sharma", "MS Dhoni", "Suryakumar Yadav",
            "Jos Buttler", "Hardik Pandya"]
bowlers = ["Bumrah", "Chahal", "Rashid Khan", "Jadeja", "Bhuvneshwar Kumar"]

for n in batters:
    add(f"How many IPL runs has {n} scored?", "batting_stats", bat(n)["runs"])
    add(f"What is {n}'s strike rate in the death overs?", "batting_stats",
        bat(n, phase="death")["strike_rate"])
for n in bowlers:
    add(f"How many IPL wickets has {n} taken?", "bowling_stats", bowl(n)["wickets"])
    add(f"What is {n}'s economy rate in the powerplay?", "bowling_stats",
        bowl(n, phase="powerplay")["economy"])

pairs = [("Kohli", "Bumrah"), ("Rohit Sharma", "Rashid Khan"),
        ("MS Dhoni", "Chahal"), ("Suryakumar Yadav", "Jadeja")]
for b, w in pairs:
    add(f"How many runs has {b} scored against {w}?", "batter_vs_bowler",
        h2h(b, w)["runs"])

json.dump(cases, open("tests/golden.json", "w"), indent=2)
print(len(cases), "cases written")