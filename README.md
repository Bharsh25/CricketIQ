# CricketIQ: IPL Match Analyst

An AI agent that answers questions about IPL cricket from ball-by-ball data. Ask about a player, a matchup, a phase of play or a team's recent form. The agent picks the right tool, runs the query, and returns the answer with a scorecard and the query behind it.

**Live demo:** https://cricketiq-9rwc.onrender.com

The demo runs on a free tier. The first request after a quiet period can take up to a minute while the service wakes up, and conversation memory resets when it redeploys.

![CricketIQ interface](docs/screenshot.png)

## Example questions

- How many IPL runs has Kohli scored?
- What is Bumrah's economy rate in the powerplay?
- How has Rohit Sharma done against Rashid Khan?
- How has Mumbai Indians done in their last five matches?
- Who has hit the most sixes in the death overs?
- What is a powerplay?

## How it works

```
Browser (static HTML, CSS, JS)
        |
FastAPI  (/chat, /players, /tools, /health)
        |
LangGraph agent:  agent  ->  tools  ->  agent  ->  verify
        |
Tools
  - batting_stats, bowling_stats, batter_vs_bowler,
    team_recent_form, venue_info        (parameterised queries)
  - sql_query                           (guarded, read-only, last resort)
  - cricket_knowledge                   (RAG over match summaries and glossary)
        |
Data
  - DuckDB over Parquet                 (matches, deliveries)
  - Chroma                              (embeddings for RAG)
  - SQLite                              (conversation memory)
```

**Design decisions**

- **Numbers come from tools, never from RAG.** Averages, strike rates and wicket counts are computed in DuckDB. RAG is used only for text: match summaries and cricket definitions.
- **Parameterised tools first, raw SQL last.** The dedicated tools cover the common questions. `sql_query` handles leaderboards and custom aggregations, and only runs `SELECT` statements on an allowlist of tables, with forbidden keywords blocked and a row limit.
- **Grounding check.** After each answer, a verify step checks that every multi-digit number in the answer appears in the tool outputs of the current turn. If not, the agent is asked to re-check once.
- **Name resolution.** Player names are matched by surname and first initial (Cricsheet style, e.g. `RG Sharma`), with the most-played player winning ties and fuzzy matching as a fallback.
- **Data cleaning.** Super overs are excluded. Renamed franchises are merged (Delhi Daredevils to Delhi Capitals, Kings XI Punjab to Punjab Kings, Royal Challengers Bangalore to Bengaluru). Wickets credited to a bowler exclude run outs and retirements.
- **Conversation memory.** Follow-up questions work ("What about Dhoni?"). Each conversation uses a server-issued UUID, and the LangGraph SQLite checkpointer stores its history.

## Tech stack

| Area | Choice |
|---|---|
| Agent | LangGraph, LangChain, Groq (`openai/gpt-oss-20b`) |
| Data | Cricsheet IPL ball-by-ball JSON, pandas, DuckDB, Parquet |
| RAG | Chroma, `BAAI/bge-small-en-v1.5` via sentence-transformers |
| Matching | rapidfuzz |
| API | FastAPI, Pydantic, Uvicorn |
| UI | Plain HTML, CSS and JavaScript served by FastAPI |
| Deployment | Docker, Render |

## Data

IPL ball-by-ball data from [Cricsheet](https://cricsheet.org): 1,243 matches and 295,557 deliveries (super overs excluded). Please refer to Cricsheet's terms for data use.

## Evaluation

Two test sets run against the real agent.

| Set | Cases | Result |
|---|---|---|
| Tool-grounded stat questions (batting, bowling, head to head) | 26 | 26/26 correct tool and correct answer |
| Edge cases | 10 | 10/10 |

The edge cases cover an unknown player, a non-IPL format, a request to predict a future match, a prompt-injection attempt, a glossary question, a two-player comparison, a follow-up question, a venue filter, team form and the SQL fallback.

Expected values for the first set are generated from the project's own database tools. The evaluation therefore tests that the agent chooses the right tool and relays its output faithfully. It does not independently validate the SQL logic.

**Bugs found by the evaluation**

- "Rohit Sharma" resolved to a different player (`R Sharma`) instead of `RG Sharma`. Fixed with surname and initial matching.
- Generated SQL counted run outs as bowler wickets by using `is_wicket`. Fixed by documenting the rule in the SQL tool's schema description.
- A stored expected value was stale after the name fix.
- Persistent memory let reused thread IDs answer from earlier runs without calling a tool. Each evaluation run now uses fresh thread IDs.

## Limitations

- IPL only. No live scores and no predictions.
- The grounding check confirms numbers come from a tool output. It does not check that a generated SQL query means what the user asked, and it skips single-digit numbers.
- The free Groq tier limits tokens per minute, so heavy traffic can return a "busy" message.
- On the free host, the first request after idle is slow, and conversation memory resets on redeploy.

## Abuse protection

The API applies a per-IP rate limit, a global daily request cap (`DAILY_CAP`), a cap on concurrent agent runs (`MAX_CONCURRENT`), a 500-character question limit and server-issued conversation IDs.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/chat` | Ask a question. Body: `{"question": "...", "thread_id": null}` |
| GET | `/players` | Player names for the matchup builder |
| GET | `/tools` | Tool names and descriptions |
| GET | `/health` | Health check |

## Run locally

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash. macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file with your Groq key (no quotes):

```
GROQ_API_KEY=your_key_here
```

Start the server and open http://127.0.0.1:8000/

```bash
python -m uvicorn app.main:app --reload --reload-dir app
```

The processed data (`data/processed`) and the vector index (`data/chroma`) are included in the repository, so no data setup is needed.

**Rebuild the data (optional)**

Download the IPL JSON files from Cricsheet into `data/raw/ipl/`, then:

```bash
python scripts/ingest.py
rm -rf data/chroma
PYTHONPATH=. python scripts/build_rag.py
```

**Run the tests and evaluations**

```bash
python -m pytest tests -q
PYTHONPATH=. python scripts/make_golden.py
PYTHONPATH=. python scripts/eval.py
PYTHONPATH=. python scripts/eval_hard.py
```

**Docker**

```bash
docker build -t cricketiq .
docker run --rm -p 8000:8000 --env-file .env cricketiq
```

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `GROQ_API_KEY` | Groq API key (required) | none |
| `DAILY_CAP` | Maximum chat requests per day | 300 |
| `MAX_CONCURRENT` | Maximum agent runs at the same time | 2 |

## Project structure

```
app/
  main.py            API routes and abuse protection
  db.py              DuckDB connection over Parquet
  resolve.py         Player and team name resolution
  agent/graph.py     LangGraph agent and grounding check
  tools/             stats tools, guarded SQL tool, RAG tool, tool registry
static/              index.html, style.css
scripts/             ingest, build_rag, make_golden, eval, eval_hard
tests/               unit tests and golden sets
data/                processed Parquet files and Chroma index
Dockerfile
```

## Author

Harsh Bhendarkar ([@Bharsh25](https://github.com/Bharsh25))
