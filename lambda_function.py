"""agentrecall daily send - AWS Lambda handler.

Invoked on a schedule. For every active order, retrieves that player's
thieves from CockroachDB, finds coaching material they have not been sent
before, composes an if-then plan with Bedrock, sends it via SES, and
records the send so tomorrow's retrieval excludes it.
"""
import os, json, boto3, pg8000.dbapi, ssl
from urllib.parse import urlparse, unquote

REGION = os.environ.get("AWS_REGION", "us-east-1")
EMBED_MODEL = "amazon.titan-embed-text-v2:0"
CHAT_MODEL = "amazon.nova-lite-v1:0"

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
ses = boto3.client("ses", region_name=REGION)


def connect():
    u = urlparse(os.environ["DB_URL"])
    ctx = ssl.create_default_context()
    return pg8000.dbapi.connect(
        user=unquote(u.username),
        password=unquote(u.password),
        host=u.hostname,
        port=u.port or 26257,
        database=u.path.lstrip("/").split("?")[0],
        ssl_context=ctx,
    )


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


def send_one(cur, order_id, email):
    cur.execute("SELECT habits FROM thieves WHERE order_id = %s", (order_id,))
    row = cur.fetchone()
    if not row:
        return {"order_id": str(order_id), "status": "no thief record"}
    habits = row[0]

    cur.execute("SELECT count(*) FROM sends WHERE order_id = %s", (order_id,))
    day_index = cur.fetchone()[0] + 1
    if day_index > 66:
        return {"order_id": str(order_id), "status": "window complete"}

    focus = habits[(day_index - 1) % len(habits)]
    thief_vec = str(embed(focus))

    cur.execute(
        "SELECT corpus_id, body FROM corpus "
        "WHERE corpus_id NOT IN (SELECT corpus_id FROM sends WHERE order_id = %s) "
        "ORDER BY embedding <-> %s LIMIT 1",
        (order_id, thief_vec),
    )
    hit = cur.fetchone()
    if not hit:
        return {"order_id": str(order_id), "status": "corpus exhausted"}
    corpus_id, body = hit

    plan = compose(focus, habits, body)

    resp = ses.send_email(
        Source=os.environ["SES_FROM"],
        Destination={"ToAddresses": [os.environ.get("SES_TO") or email]},
        Message={
            "Subject": {"Data": "Your sleepfix - day " + str(day_index) + " of 66"},
            "Body": {"Text": {"Data": plan + "\n\n-- agentrecall"}},
        },
    )

    cur.execute(
        "INSERT INTO sends (order_id, corpus_id, day_index, plan_text) "
        "VALUES (%s, %s, %s, %s)",
        (order_id, corpus_id, day_index, plan),
    )
    return {
        "order_id": str(order_id),
        "day": day_index,
        "focus": focus,
        "message_id": resp["MessageId"],
    }


def lambda_handler(event, context):
    conn = connect()
    cur = conn.cursor()
    results = []
    try:
        cur.execute("SELECT order_id, email FROM orders WHERE status = 'active'")
        for order_id, email in cur.fetchall():
            results.append(send_one(cur, order_id, email))
        conn.commit()
    finally:
        conn.close()
    return {"sent": len(results), "results": results}