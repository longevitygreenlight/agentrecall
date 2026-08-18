import os, json, boto3, psycopg2

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
conn = psycopg2.connect(os.environ["DB_URL"])
cur = conn.cursor()

def embed(text):
    r = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text}),
    )
    return json.loads(r["body"].read())["embedding"]

cur.execute("SELECT corpus_id, habit_tag, body FROM corpus WHERE embedding IS NULL")
rows = cur.fetchall()
print(f"embedding {len(rows)} rows")

for corpus_id, tag, body in rows:
    vec = embed(f"{tag}: {body}")
    cur.execute(
        "UPDATE corpus SET embedding = %s WHERE corpus_id = %s",
        (str(vec), corpus_id),
    )
    conn.commit()
    print(".", end="", flush=True)

print("\ndone")
