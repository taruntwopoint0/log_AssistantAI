# AI Investigation Assistant

Paste an error block. Get the failure layer, a confidence band, the evidence behind it,
matching past incidents, and the runbook fix.

Built for **LEAP Young Innovators 2026, theme 3 (Log Analysis)**, against a real
BulkSuppliers sync failure.

---

## The design principle

**Code decides. The model writes.**

Every decision — which layer failed, how confident we are — is made by deterministic
Python. The LLM only turns that decision into prose.

- If the model hallucinates, we get an awkward sentence, not a wrong root cause.
- If the model is unavailable, the tool still works. We lose a paragraph.

`engine/writer.py` is the only file that imports an SDK or opens a socket. Stages 1–6
are stdlib-only: regex, dict lookups and arithmetic. That is what makes the whole
decision path unit-testable offline, and it is the reliability argument for running
this in a bank.

**The diagnosis is not RAG.** Stages 1–7 look runbooks and topology up by key, never
semantically, and the model receives the conclusion as a finished fact.

**Ask the Diagnosis does retrieve** — but over *verified facts*, not documents. The
retrievable set is 17 allowlisted functions whose outputs are the deterministic
investigation, the config, the knowledge graph and the precedent matches. There is no
document store, no chunking and no query language the model can write into; it picks
a lookup by name and the backend runs it. So the pipeline never becomes
`logs → RAG → LLM → guessed diagnosis`. The diagnosis is already settled before a
single question can be asked about it.

---

## Run

```bash
cd backend
pip install -r requirements.txt
python gen_mock_logs.py
uvicorn main:app --reload --port 8000
```

Open <http://localhost:8000>.

The Gemini key is **optional**. Without it the tool runs stage 7 through a
deterministic template and everything else is identical:

```bash
set GEMINI_API_KEY=...
```

Model defaults to `gemini-3.5-flash-lite`, overridable with `GEMINI_MODEL`.
Never commit the key. It is read server-side only — the React page never holds it.

Tests:

```bash
python -m pytest tests/ -q
```

235 tests, under a second, no network and no key required.

---

## Architecture

```
React dashboard (single HTML file, CDN React, no build step)
        │  POST /api/investigate
FastAPI (backend/main.py)
        │
Engine  ├── 1–2  parser.py       regex → typed Evidence
        ├── 3    parser.py       derived: elapsed, seconds-per-record, projection
        ├── 4    rules_engine.py matches rules.json → layer          ← no AI
        ├── 5    knowledge.py    topology + runbooks → owner, fix    ← no AI
        ├── 5b   precedent.py    past resolved incidents             ← no AI
        ├── 6    scorer.py       5 dimensions + coverage cap → band  ← no AI
        └── 7    writer.py       the model writes the prose          ← ONLY AI
```

`pipeline.py` is the whole tool in one readable function.

On top of the finished diagnosis sits the conversational layer:

```
POST /api/ask
│
├── PROJECT  query_assistant.py -> query_tools.py  17 allowlisted lookups
│                              -> graph.py         what is connected
│                              -> precedent.py     what is similar
│            The model picks a lookup and explains the result. It never
│            executes anything and never sees the raw log.
│
└── GENERAL  The model's own knowledge, told explicitly that this is not
             evidence about the current incident.
```

    Code decides what happened.
    Graph explains what is connected.
    Vector search finds what is similar.
    The model understands the question and explains verified facts.

---

## Ask the Diagnosis

A conversational layer over the finished investigation, in two explicit modes.

**PROJECT - Grounded.** The model may use nothing except the output of 17
allowlisted functions in `engine/query_tools.py`. It cannot query anything, cannot
reach the raw log, and cannot alter the layer, the band, the evidence or the
eliminations. If the lookups come back empty it says so:

> *"I don't have sufficient project evidence to determine that."*

**GENERAL - AI knowledge.** Ordinary technical questions ("what is a 504?"), with a
hard instruction not to pass generic knowledge off as evidence about this incident.

### How a question gets answered

1. A **deterministic keyword router** picks the lookups. Every question in the
   original brief routes without a model call at all, which halves latency and keeps
   routing reproducible. The model is asked to choose only when the keywords shrug -
   and anything it invents is dropped against the allowlist rather than executed.
2. The **backend** runs the lookups. The model never does.
3. The results, each carrying its provenance, are the only facts in the prompt.
4. Internal identifiers are tokenised on the way out, exactly as in `writer.py`.

Every answer shows its origin: `source: topology.json (layers[].owner)` /
`lookups: get_owner, get_application (chosen by keywords)`.

With no API key, PROJECT mode still answers - a deterministic formatter renders the
same verified facts. Only the phrasing is lost.

### The knowledge graph

`engine/graph.py` builds ~70 nodes and ~120 edges from the four JSON config files
plus the current investigation. No graph database, and no query language the model
can write into: the only traversal primitive is a fixed chain of relations.

"Which team owns this?" is a walk, not a lookup:

```
Incident:CURRENT --CLASSIFIED_AS--> Layer:GatewayTimeout --OWNED_BY--> Team
```

Node types: Application, Service, API, Database, Host, Team, Layer, Runbook, Source,
Incident, Evidence, Fix.

### Vector search

`config/topology.json` chooses the precedent backend. **Ships with vectors on:**

```json
"precedent": { "backend": "embeddings" }
```

`embeddings` does cosine similarity over the **normalised signature only** - never a
raw stack trace - and falls back to `lexical` automatically if the key or network is
missing. `lexical` is deterministic Dice-coefficient matching that needs nothing. The
test suite pins `lexical` via `conftest.py` so it stays offline and reproducible.

Signatures are cached in `embedding_cache.json` keyed by the signature string, so a
recurring fault is embedded once. Warm the cache before a demo; a cached investigation
runs in ~4ms.

**What vectors actually buy.** A past incident written up in an engineer's own words
rather than yours:

| | lexical | embeddings |
|---|---|---|
| `socket closed by upstream proxy before body finished` vs `response ended prematurely` | 0.133 | **0.687** |
| total match score | 0.610 | **0.859** |

Lexical rates the same failure, differently described, as a weak match. Vectors
recognise it.

**Identical shapes are grouped.** Four incidents sharing one signature used to fill
the whole result window and crowd out genuinely different faults. They now collapse
into one representative - the most recent - carrying a `recurrence` count. "Seen 4
times, fix held every time" is better information than four near-identical rows.

**Calibrate before trusting it.** Raw cosine over short technical strings is badly
compressed. Measured against the real model:

| pair | lexical | raw cosine | calibrated |
|---|---|---|---|
| "response ended prematurely" vs "connection terminated early" | 0.40 | 0.965 | **0.826** |
| "response ended prematurely" vs "SQL pool size was reached" | 0.00 | **0.827** | **0.133** |

Two unrelated failures scored 0.827 raw - on its own enough to clear
`MIN_SIMILARITY` on the signature component, which is precisely what the weighting
exists to prevent. `embeddings.SIMILARITY_FLOOR` rescales the usable band, and it is
the one number to tune against your own incidents.

---

## Config, not code

All domain knowledge lives in four JSON files. Another team adapts this by editing
them — no code change, no recompile.

| File | Holds |
|---|---|
| `config/topology.json` | sources, layers, owners, runbook ids, hosts, throughput baseline, known ceilings |
| `config/rules.json` | evidence → layer, and what each rule eliminates |
| `config/runbooks.json` | symptom, checks, fix, and what **not** to do |
| `config/incidents.json` | resolved incidents for precedent matching |

`POST /api/config/reload` picks up edits without restarting the server, so the
portability claim is demonstrable live.

---

## The production case

18 Aug 2026, BulkSuppliers worker. Every failure lands at ~60 seconds, and only on
large batches:

| Time | Records | Outcome | Elapsed |
|---|---|---|---|
| 08:46 | 2, 6, 1 | 200 OK | 1–2 s |
| 11:03 | 39 | 200 OK | 7 s |
| 11:20 | 539 | ERR | 62 s |
| 11:23 | 537 | ERR | 60 s |

39 records in 7 s is 0.179 s/record. The tool measures that rate **from the same log**
rather than assuming it, then projects: 539 records needs **≈97 s**. The call died at
60 s. .NET's default HttpClient timeout is 100 s, so the client is not the cutter.

Galileo is not down — it answers small batches all day. Something with a hard
60-second ceiling is cutting the connection mid-response.

The manual seven-step checklist concludes "Galileo reachable, DB fine, service
running" and stalls. This gets to "intermediary timeout on large payloads, chunk to
200 records" — a fix inside our control and testable today.

---

## Confidence scoring

Scored from properties of the **evidence**, never asked of the model. A model rating
its own confidence answers 90% every time.

| Dimension | Weight | Measures |
|---|---|---|
| Corroboration | 0.30 | independent **sources** that agree (not line count) |
| Elimination | 0.25 | how many candidate layers were ruled out |
| Specificity | 0.20 | does the evidence pin one layer or fall through |
| Precedent | 0.15 | seen before, and did the fix hold |
| Temporal | 0.10 | how tight the evidence is to the failure |

The **band** is a word — High / Medium / Inconclusive — and it is what the tool
commits to. A word survives being wrong; a number invites an argument about the
number.

The underlying **evidence score** is shown alongside it as a percentage, because
hiding it made the coverage cap look arbitrary. Seeing "91% evidence score — would be
High, capped" is a much clearer account of what happened than "Medium" on its own.
Note the label: it scores the *evidence*, and it is computed by `scorer.py`. It is not
the model's opinion of its own output, and the UI never calls it one.

### The coverage cap

With 3 of 7 sources connected, the band is ceilinged at **Medium** however clean the
evidence looks. Silence from a disconnected source is not evidence of health. This
blocks the worst failure mode a tool like this has: a partially deployed system
producing high-confidence wrong answers because the sources that would have
contradicted it were never wired up.

Two hard overrides:

- A layer of `Unknown` is always `Inconclusive`, whatever the surrounding evidence scored.
- The cap can only lower a band, never raise one. Full coverage does not promote thin evidence.

---

## The eight scenarios

All verified by `tests/test_scenarios.py`. Raw score is the uncapped weighted sum.

| Sample | Concludes | Band | Raw | Uncapped |
|---|---|---|---|---|
| `gateway_timeout` | GatewayTimeout | Medium | 0.905 | High |
| `auth_401` | Auth | Medium | 0.951 | High |
| `galileo_down` | GalileoDown | Medium | 0.891 | High |
| `network_refused` | Network | Medium | 0.887 | High |
| `service_crash` | WindowsService | Medium | 0.830 | High |
| `db_failure` | AldavarDB | Medium | 0.710 | High |
| `healthy_run` | Healthy | Medium | 0.645 | Medium |
| `unrecognised` | Unknown | **Inconclusive** | 0.175 | Inconclusive |

`unrecognised` is the most important case: the evidence matches no rule and the system
declines to guess rather than inventing a cause. It still shows what it looked at.

**Known weakness:** six of eight scenarios reach High uncapped, so today the coverage
cap is doing most of the discriminating and the raw score separates strong from weak
evidence less than it should. See *Next* below.

---

## Demo moments

1. **The timing ruler** — the 60 s cut-off against the ≈97 s that 539 records actually
   need, with the 100 s client limit marked to rule the client out. That one graphic
   is the root cause.
2. **The "all 7 sources connected" toggle** — same log, band moves Medium → High, and
   the root cause, the rule, and the eliminations are all provably unchanged
   (`test_coverage_toggle_never_changes_the_root_cause`).
3. **`unrecognised`** — the system saying "I don't know, here's what I checked."

---

## Measuring accuracy

Every investigation writes a row to `predictions.jsonl` (gitignored). Attach the true
cause later and the tool reports accuracy **per band**:

```bash
curl -X POST localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"prediction_id":"...","actual_layer":"GatewayTimeout"}'

curl localhost:8000/api/accuracy
```

A band is only meaningful if High is right more often than Medium. This is the
endpoint that proves or disproves that, and it is why the log is worth keeping from
the first demo rather than retrofitted after.

---

## Vector search — the swap point

`engine/precedent.py::_similarity()` is the only function that changes. Replace its
body with cosine similarity over embeddings and nothing downstream moves: same
signature, same threshold semantics, same output. `tests/test_precedent.py` is the
contract — every test in it should still pass unchanged.

**Do not embed raw stack traces.** GUIDs, timestamps and thread ids dominate the
vector and produce confident matches on boilerplate every .NET exception shares. Embed
`_signature_key()` output: exception chain plus inner symptom, with layer, host and
size/timing buckets carried as separate weighted components.

Current weighting is lexical: 0.45 signature, 0.35 layer, 0.10 host, 0.10 facts.
Deliberately top-heavy so an unrelated incident cannot drift into range on host alone.

---

## Constraints and decisions

- **Read-only by design.** No restarts, no remediation, no writes to any monitored
  system. The only thing written is the local prediction log. This is what clears risk review.
- **Gemini is PoC only.** Outside the bank's tenancy — fine for a demo on mock logs,
  not for production content. Production target is the approved Azure OpenAI endpoint.
  `engine/writer.py` is the only file that changes.
- **Python for the hackathon, .NET for the team.** Production stack is React + .NET 10
  Web API + Azure OpenAI. The port is mechanical — the domain knowledge is in JSON and
  carries over unchanged — but it is bigger than the original estimate of ~450 lines.
  Measured: **1,290 executable lines** in `engine/`, of which `writer.py` (155) is
  replaced rather than ported, leaving **~1,135 lines** to translate. `parser.py` is
  479 of those and is mostly a regex vocabulary that maps to .NET directly.
- **Grafana** is a dashboard tool (needs Loki + Alloy to read log files) with no
  analysis capability. Charts are already in the React dashboard, so it is a roadmap
  slide, not a build item.
- **No auto-tailing in the PoC.** Design exists: trigger on `ERR`, capture the whole
  multi-line block (ends at the next `HH:MM:SS LVL` line — this is exactly what
  `parser.build_blocks` already does), keep a rolling 5-minute buffer because the
  diagnosis lives *before* the error, and group repeat failures by signature over a
  5-minute window to avoid storms.

### Demo risk

The dashboard loads React and Babel from unpkg. **If the demo machine has no internet
or the CDN is blocked, the page renders blank.** Vendor the three files into
`backend/static/vendor/` and change the `src` attributes before demoing on a bank
network.

---

## Next

1. Run the parser against **real** log files and fix format edge cases. The header
   matcher already accepts 8 Serilog layouts (`tests/test_parser.py::FORMATS`) but
   your sink config is the real test.
2. Hand-classify 15–20 past resolved incidents into `config/incidents.json` and expand
   `rules.json`, then use `/api/accuracy` for a real figure in the pitch.
3. Tune the scoring weights so raw score discriminates better — right now the cap does
   most of the work.
4. Later: the .NET port, and swapping `_similarity()` for embeddings.
