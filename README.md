# agentrecall

CockroachDB memory layer under an a2a buyer/seller agent pair: it remembers the sleep thieves a sleepfix finds and coaches the fix by email for 66 days.

## The problem

You find your sleep thieves, then nothing remembers them tomorrow.

A sleep assessment gives you a result and ends. The habits it identified are gone by the next evening — the moment you would actually need them. Coaching that does not persist is not coaching.

## What agentrecall does

agentrecall is the memory layer under an existing buyer/seller agent pair selling a sleepfix for 0.88 USDC.

1. **Purchase.** A buyer agent verifies the customer's email, then posts to the seller's a2a endpoint with payment and the verified address. An `orders` row is written and the sleepfix link returned.
2. **Game finish.** The player finishes a 58-second round. The raw wrong answers land in `evidence`; the interpreted habits land in `thieves` as one record that may hold several habits. This split matters — what was captured stays separate from what was concluded.
3. **Daily coaching.** Each day an agent retrieves this player's thieves, searches the coaching corpus by vector similarity while **excluding everything already sent to them**, and has Bedrock compose a fresh if-then plan from what it found. The send is recorded, which is what makes the exclusion work tomorrow.

The 66-day window comes from the median time to habit automaticity (Lally et al., 2010: median 66 days, range 18–254). It is the length of the coaching window, not a promised outcome.

## Why memory is the product, not a feature

Strip CockroachDB out and there is nothing left. The agent has no idea who it is writing to, which habits to address, or what it already said. Specifically:

- **`thieves`** is the durable identity of the problem. Written once, read every day for 66 days.
- **`corpus.embedding`** with a distributed vector index is what makes retrieval semantic rather than a lookup table. The agent finds material *close to* this player's habit, not material tagged with it.
- **`sends`** is the anti-repetition memory. The daily query excludes every `corpus_id` already sent to this order, so day 40 cannot repeat day 3. This is the single most important line of SQL in the project.
- **Habit rotation.** When a player has more than one thief, the retrieval focus rotates by day index. Without this, the densest cluster in the corpus monopolises the whole window — an early version sent three caffeine plans in a row before this was fixed.

## Architecture

```
buyer agent  ──POST 0.88 USDC + verified email──>  seller a2a endpoint
                                                          │
                                                    orders row
                                                          │
player plays sleepfix ──POST /result──>  evidence row + thieves row
                                                          │
                                          Bedrock Titan embeds the record
                                                          │
                        ┌─────────────── CockroachDB ───────────────┐
                        │  orders · evidence · thieves · corpus     │
                        │  sends   · VECTOR INDEX on corpus         │
                        └───────────────────────────────────────────┘
                                                          │
daily run ──> read thieves + sends ──> vector search corpus (minus sent)
                                                          │
                                    Bedrock Nova composes an if-then plan
                                                          │
                                              SES email ──> sends row
```

## CockroachDB tools used

**Distributed Vector Indexing.** The `corpus` table stores 1024-dimension embeddings in a `VECTOR(1024)` column with `CREATE VECTOR INDEX corpus_embedding_idx ON corpus (embedding)`. The daily agent's retrieval is a `ORDER BY embedding <-> $1 LIMIT 1` nearest-neighbour search with a `NOT IN` exclusion against the sends table. Vectors and operational data live in the same database, so there is no consistency gap between "what was sent" and "what is available to send" — with a separate vector store, that exclusion would be a distributed join across two systems.

**CockroachDB Cloud Managed MCP Server.** Configured at `.vscode/mcp.json` (HTTP transport, cluster-id header, no credentials in the file) so an MCP-capable agent client can explore the schema and inspect queries against the live cluster.

## AWS services used

- **Amazon Bedrock — Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`) embeds the coaching corpus and the daily retrieval focus. 1024 dimensions, matching the `VECTOR(1024)` column.
- **Amazon Bedrock — Nova Lite** (`amazon.nova-lite-v1:0`) composes each day's if-then plan from the retrieved material, scoped to the focus habit.
- **Amazon SES** is the delivery channel for the coaching emails.
- The cluster itself runs on **AWS** (CockroachDB Basic, eu-west-1).

## Running it

Requires Python 3.12+, a CockroachDB Cloud cluster, and AWS credentials with Bedrock access.

```bash
pip install boto3 psycopg2-binary

# CockroachDB CA certificate (once)
curl --create-dirs -o ~/.postgresql/root.crt \
  https://cockroachlabs.cloud/clusters/<your-cluster-id>/cert

export DB_URL="postgresql://<user>:<password>@<host>:26257/<db>?sslmode=verify-full"
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
```

Create the schema from `schema.sql`, load the coaching corpus from `corpus_seed.sql`, then:

```bash
python3 embed_corpus.py                  # embeds every corpus row that has no vector
python3 daily_agent.py <order_id>        # runs one day for one order
```

Each run of `daily_agent.py` advances that order by one day, picks material it has not used before, and records the send.

## Honest limitations

- **The corpus is smaller than the window.** 30 coaching entries across 10 habit labels against a 66-day window. Retrieval is exhausted around day 30. The mechanism is complete; the content library is not, and growing it is straightforward — new rows only need a `habit_tag`, a body, and an embedding.
- **The daily run is invoked manually** in this build. Production scheduling is EventBridge on a fixed hour.
- **The buyer and seller agents are existing components**, not built for this hackathon. What is new here is the memory layer underneath them.

## Licence

MIT.