import { Hono } from 'hono';

type Bindings = {
  DB: D1Database;
};

const app = new Hono<{ Bindings: Bindings }>();

const corsHeaders = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET,POST,OPTIONS',
  'access-control-allow-headers': 'content-type',
  'access-control-expose-headers': 'x-generated-at',
};

app.options('/*', c => new Response(null, { headers: corsHeaders }));

function jsonResponse(body: string, status = 200, extraHeaders: Record<string, string> = {}) {
  return new Response(body, {
    status,
    headers: {
      'content-type': 'application/json',
      ...corsHeaders,
      ...extraHeaders,
    },
  });
}

// Fetch latest payload for a pair/interval.
app.get('/latest', async c => {
  const pair = c.req.query('pair');
  const intervalSec = Number(c.req.query('interval_sec') ?? 3600);
  const kind = c.req.query('kind'); // optional: recommendations | prices | raw
  if (!pair || Number.isNaN(intervalSec)) {
    return new Response('pair and interval_sec required', { status: 400, headers: corsHeaders });
  }

  const { results } = await c.env.DB.prepare(
    'SELECT payload, generated_at FROM rec_runs WHERE pair = ? AND interval_sec = ? ORDER BY generated_at DESC LIMIT 1'
  )
    .bind(pair, intervalSec)
    .all();

  if (!results.length) {
    return new Response('not found', { status: 404, headers: corsHeaders });
  }

  const raw = results[0].payload as string;
  const generatedAt = Number(results[0].generated_at ?? 0);
  try {
    const parsed = JSON.parse(raw);
    if (kind === 'recommendations' && parsed?.recommendations) {
      return jsonResponse(JSON.stringify(parsed.recommendations), 200, {
        'x-generated-at': String(generatedAt),
      });
    }
    if (kind === 'prices' && parsed?.prices) {
      return jsonResponse(JSON.stringify(parsed.prices), 200, {
        'x-generated-at': String(generatedAt),
      });
    }
  } catch {
    // fallthrough to raw response
  }
  return jsonResponse(raw, 200, { 'x-generated-at': String(generatedAt) });
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
  if (!pair || !interval_sec || !generated_at || payload == null) {
    return new Response('missing fields', { status: 400, headers: corsHeaders });
  }

  await c.env.DB.prepare(
    'INSERT OR REPLACE INTO rec_runs (pair, lookback, interval_sec, generated_at, payload) VALUES (?,?,?,?,?)'
  )
    .bind(pair, Number(lookback) || 0, Number(interval_sec), Number(generated_at), JSON.stringify(payload))
    .run();

  return new Response('ok', { status: 200, headers: corsHeaders });
});

app.get('/health', c => new Response('ok', { status: 200, headers: corsHeaders }));

export default app;
