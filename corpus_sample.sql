-- agentrecall corpus SAMPLE
--
-- The production coaching corpus is not included in this repository.
-- These rows are placeholder text in the correct shape, so the setup
-- instructions in the README can be followed end to end: load this,
-- run embed_corpus.py, then run daily_agent.py.
--
-- Shape: one row per coaching entry. habit_tag matches a thief label
-- stored in thieves.habits. body is the source material the agent
-- composes from. embedding is filled by embed_corpus.py.

INSERT INTO corpus (habit_tag, body) VALUES
  ('caffeine', 'Caffeine has a long half-life, so a drink taken in the afternoon is still active in the body at bedtime. Moving the last cup earlier in the day gives the body time to clear it before the lights go down.'),
  ('caffeine', 'The effect is dose-dependent and cumulative across a day. Counting total intake rather than only the last drink often explains a night that felt inexplicably wakeful.'),
  ('racing-mind', 'An unfinished thought keeps its own claim on attention. Writing tomorrow down before bed hands that claim to the page, and the mind stops rehearsing it in the dark.'),
  ('racing-mind', 'Lying awake trying to sleep raises the effort involved. Getting up briefly and returning when drowsy breaks the association between the bed and the struggle.'),
  ('screen-light', 'Bright light late in the evening delays the internal signal that night has arrived. Dimming the room an hour before bed lets that signal arrive on time.'),
  ('late-meal', 'Digestion competes with the settling the body does at the start of the night. An earlier dinner leaves the work finished before sleep begins.');