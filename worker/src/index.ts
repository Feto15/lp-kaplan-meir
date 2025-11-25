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

type PriceRow = {
  ts: number;
  price: number;
  block?: number;
};

// Fetch latest payload for a pair/interval (legacy rec_runs, ignores lookback).
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

// Fetch latest survival run with lookback awareness.
app.get('/latest_survival', async c => {
  const pair = c.req.query('pair');
  const lookback = Number(c.req.query('lookback') ?? 0);
  const intervalSec = Number(c.req.query('interval_sec') ?? 3600);
  if (!pair || Number.isNaN(lookback) || Number.isNaN(intervalSec)) {
    return new Response('pair, lookback, interval_sec required', { status: 400, headers: corsHeaders });
  }

  const { results } = await c.env.DB.prepare(
    'SELECT payload, generated_at FROM survival_runs WHERE pair = ? AND lookback = ? AND interval_sec = ? ORDER BY generated_at DESC LIMIT 1'
  )
    .bind(pair, lookback, intervalSec)
    .all();

  if (!results.length) {
    return new Response('not found', { status: 404, headers: corsHeaders });
  }

  const raw = results[0].payload as string;
  const generatedAt = Number(results[0].generated_at ?? 0);
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

// Append raw price rows (incremental ingest).
app.post('/append_prices', async c => {
  let body: any;
  try {
    body = await c.req.json();
  } catch {
    return c.text('invalid json', 400);
  }

  const { pair, rows } = body as { pair?: string; rows?: PriceRow[] };
  if (!pair || !Array.isArray(rows) || rows.length === 0) {
    return new Response('pair and non-empty rows required', { status: 400, headers: corsHeaders });
  }

  const stmt = c.env.DB.prepare('INSERT OR REPLACE INTO prices (pair, ts, price, block) VALUES (?, ?, ?, ?)');
  for (const row of rows) {
    if (!row || Number.isNaN(Number(row.ts)) || Number.isNaN(Number(row.price))) {
      continue;
    }
    await stmt.bind(pair, Number(row.ts), Number(row.price), row.block != null ? Number(row.block) : null).run();
  }

  return new Response('ok', { status: 200, headers: corsHeaders });
});

// Get last timestamp for a pair in prices table.
app.get('/last_ts', async c => {
  const pair = c.req.query('pair');
  if (!pair) {
    return new Response('pair required', { status: 400, headers: corsHeaders });
  }
  const { results } = await c.env.DB.prepare('SELECT MAX(ts) AS last_ts FROM prices WHERE pair = ?')
    .bind(pair)
    .all();
  const last = results[0]?.last_ts;
  if (last == null) {
    return new Response('not found', { status: 404, headers: corsHeaders });
  }
  return jsonResponse(JSON.stringify({ last_ts: Number(last) }));
});

// Ingest precomputed survival/recommendation payload keyed by lookback+interval.
app.post('/ingest_survival', async c => {
  let body: any;
  try {
    body = await c.req.json();
  } catch {
    return c.text('invalid json', 400);
  }

  const { pair, lookback, interval_sec, generated_at, payload } = body;
  if (!pair || lookback == null || interval_sec == null || generated_at == null || payload == null) {
    return new Response('missing fields', { status: 400, headers: corsHeaders });
  }

  await c.env.DB.prepare(
    'INSERT OR REPLACE INTO survival_runs (pair, lookback, interval_sec, generated_at, payload) VALUES (?,?,?,?,?)'
  )
    .bind(pair, Number(lookback), Number(interval_sec), Number(generated_at), JSON.stringify(payload))
    .run();

  return new Response('ok', { status: 200, headers: corsHeaders });
});

app.get('/health', c => new Response('ok', { status: 200, headers: corsHeaders }));

export default app;
