import { Hono } from 'hono';

type Bindings = {
  DB: D1Database;
};

const app = new Hono<{ Bindings: Bindings }>();

// Fetch latest payload for a pair/interval.
app.get('/latest', async c => {
  const pair = c.req.query('pair');
  const intervalSec = Number(c.req.query('interval_sec') ?? 3600);
  if (!pair || Number.isNaN(intervalSec)) return c.text('pair and interval_sec required', 400);

  const { results } = await c.env.DB.prepare(
    'SELECT payload FROM rec_runs WHERE pair = ? AND interval_sec = ? ORDER BY generated_at DESC LIMIT 1'
  )
    .bind(pair, intervalSec)
    .all();

  if (!results.length) return c.text('not found', 404);
  return new Response(results[0].payload as string, {
    headers: { 'content-type': 'application/json' },
  });
});

// Ingest a new run (one row per timestamp).
app.post('/ingest', async c => {
  let body: any;
  try {
    body = await c.req.json();
  } catch {
    return c.text('invalid json', 400);
  }

  const { pair, lookback = 0, interval_sec, generated_at, payload } = body;
  if (!pair || !interval_sec || !generated_at || payload == null) return c.text('missing fields', 400);

  await c.env.DB.prepare(
    'INSERT OR REPLACE INTO rec_runs (pair, lookback, interval_sec, generated_at, payload) VALUES (?,?,?,?,?)'
  )
    .bind(pair, Number(lookback) || 0, Number(interval_sec), Number(generated_at), JSON.stringify(payload))
    .run();

  return c.text('ok');
});

app.get('/health', c => c.text('ok'));

export default app;
