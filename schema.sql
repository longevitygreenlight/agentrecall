-- agentrecall schema
-- CockroachDB. Run against your cluster before loading corpus_seed.sql.

CREATE TABLE orders (
  order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email STRING NOT NULL,
  verified BOOL NOT NULL DEFAULT false,
  status STRING NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Raw wrong answers from the round: what was captured, kept separate
-- from what was concluded.
CREATE TABLE evidence (
  evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES orders(order_id),
  wrong_ids STRING[] NOT NULL,
  resolved_labels STRING[] NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One record per order, holding one or more habits. This is the durable
-- identity of the player's problem, read every day for 66 days.
CREATE TABLE thieves (
  thief_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES orders(order_id),
  habits STRING[] NOT NULL,
  summary STRING NOT NULL,
  embedding VECTOR(1024),
  day0 DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The coaching material the daily agent retrieves from.
CREATE TABLE corpus (
  corpus_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  habit_tag STRING NOT NULL,
  body STRING NOT NULL,
  embedding VECTOR(1024),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The anti-repetition memory: corpus_id here excludes that row from
-- tomorrow's retrieval for this order.
CREATE TABLE sends (
  send_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES orders(order_id),
  corpus_id UUID NOT NULL REFERENCES corpus(corpus_id),
  day_index INT NOT NULL,
  plan_text STRING NOT NULL,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE VECTOR INDEX corpus_embedding_idx ON corpus (embedding);