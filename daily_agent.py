"""agentrecall - daily coaching agent.

CockroachDB is the memory: it holds the order, the sleep thieves the sleepfix
found, the coaching corpus as vectors, and the record of what has already been
sent. Each run retrieves what this player has NOT yet seen, so day 40 never
repeats day 3.
"""
import os, json, sys, boto3, psycopg2

REGION = "us-east-1"
EMBED_MODEL = "amazon.titan-embed-text-v2:0"
CHAT_MODEL = "amazon.nova-lite-v1:0"

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
conn = psycopg2.connect(os.environ["DB_URL"])


def embed(text):
    r = bedrock.invoke_model(
        modelId=EMBED_MODEL, body=json.dumps({"inputText": text})
    )
    return json.loads(r["body"].read())["embedding"]


def compose(focus, habits, source):
    others = [h for h in habits if h != focus]
    prompt = (
        "You are a sleep coach. Today's focus habit is: "
        + focus
        + ". The player's other sleep thieves are: "
        + (", ".join(others) if others else "none")
        + ".\n\nReference material:\n"
        + source
        + "\n\nWrite ONE if-then plan about the FOCUS habit only, two sentences, "
        "warm and concrete. Start with 'If' and name a specific cue and action. "
        "Do not repeat the reference material verbatim. "
        "Do not mention herbal tea unless the reference material does."
    )
    r = bedrock.invoke_model(
        modelId=CHAT_MODEL,
        body=json.dumps(
            {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 200, "temperature": 0.8},
            }
        ),
    )
    out = json.loads(r["body"].read())
    return out["output"]["message"]["content"][0]["text"].strip()


def run(order_id):
    cur = conn.cursor()

    cur.execute(
        "SELECT habits FROM thieves WHERE order_id = %s",
        (order_id,),
    )
    habits = cur.fetchone()[0]
    print("thieves on file:", habits)

    cur.execute("SELECT count(*) FROM sends WHERE order_id = %s", (order_id,))
    day_index = cur.fetchone()[0] + 1

    # Rotate which thief drives retrieval, so a braided pair alternates
    # instead of one habit monopolising all 66 days.
    focus = habits[(day_index - 1) % len(habits)]
    print("today's focus:", focus)
    thief_vec = str(embed(focus))

    cur.execute(
        """
        SELECT corpus_id, body
        FROM corpus
        WHERE corpus_id NOT IN (
            SELECT corpus_id FROM sends WHERE order_id = %s
        )
        ORDER BY embedding <-> %s
        LIMIT 1
        """,
        (order_id, thief_vec),
    )
    row = cur.fetchone()
    if not row:
        print("corpus exhausted for this order")
        return
    corpus_id, body = row
    print("day", day_index, "- retrieved corpus row", corpus_id)

    plan = compose(focus, habits, body)
    print("\n--- plan ---")
    print(plan)
    print()

    cur.execute(
        "INSERT INTO sends (order_id, corpus_id, day_index, plan_text) "
        "VALUES (%s, %s, %s, %s)",
        (order_id, corpus_id, day_index, plan),
    )
    conn.commit()
    print("send recorded")


if __name__ == "__main__":
    run(sys.argv[1])