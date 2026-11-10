import chromadb
from sentence_transformers import SentenceTransformer
from app.db import q

model = SentenceTransformer("BAAI/bge-small-en-v1.5")
client = chromadb.PersistentClient(path="data/chroma")
col = client.get_or_create_collection("cricket_docs")

docs, ids, metas = [], [], []

# Match summaries
df = q("""SELECT match_id, date, season, venue, team1, team2, winner,
                toss_winner, toss_decision, player_of_match FROM matches""")
for r in df.itertuples():
    text = (f"On {r.date} at {r.venue}, {r.team1} played {r.team2} in IPL {r.season}. "
            f"{r.toss_winner} won the toss and chose to {r.toss_decision}. "
            f"Winner: {r.winner}. Player of the match: {r.player_of_match}.")
    docs.append(text); ids.append(f"match_{r.match_id}")
    metas.append({"type": "match", "season": str(r.season)})

# Player profiles (top batters)
top = q("""SELECT batter, SUM(runs_batter) runs, COUNT(DISTINCT match_id) m,
                    ROUND(SUM(runs_batter)*100.0/COUNT(*) FILTER (WHERE is_legal_for_batter),1) sr
            FROM deliveries GROUP BY batter HAVING SUM(runs_batter) > 1000""")
for r in top.itertuples():
    docs.append(f"{r.batter} has scored {r.runs} IPL runs in {r.m} matches at a strike rate of {r.sr}.")
    ids.append(f"player_{r.batter}"); metas.append({"type": "player"})

# Glossary
glossary = {
    "powerplay": "The first 6 overs of a T20 innings with fielding restrictions.",
    "death overs": "Overs 16 to 20, when batters attack and yorkers are common.",
    "strike rate": "Runs scored per 100 balls faced by a batter.",
    "economy rate": "Runs conceded per over by a bowler.",
}
for k, v in glossary.items():
    docs.append(f"{k}: {v}"); ids.append(f"gloss_{k}"); metas.append({"type": "glossary"})

embs = model.encode(docs, batch_size=64, normalize_embeddings=True).tolist()
for i in range(0, len(docs), 500):
    col.upsert(ids=ids[i:i+500], documents=docs[i:i+500],
                embeddings=embs[i:i+500], metadatas=metas[i:i+500])
print("Indexed", len(docs))