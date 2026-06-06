/**
 * api/server.js — AIOS Management API
 * Express 5 + WebSocket + JWT + RBAC
 * Port: process.env.PORT || 5000
 *
 * Architecture
 * ────────────
 *  • HTTP / REST  — Express 5 application mounted at /api/*
 *  • WebSocket    — ws server at /stream (live daemon event relay)
 *  • Daemon poll  — every 5 s we pull metrics from the Python daemon and
 *                   broadcast them to all connected WS clients
 *  • Relay POST   — /internal-ws-relay lets the daemon push events directly
 */

'use strict';

// ---------------------------------------------------------------------------
// Environment — load .env from project root before anything else
// ---------------------------------------------------------------------------

require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') });

// ---------------------------------------------------------------------------
// Core dependencies
// ---------------------------------------------------------------------------

const http   = require('http');
const path   = require('path');
const express = require('express');
const cors    = require('cors');
const morgan  = require('morgan');
const fetch   = require('node-fetch');
const { WebSocketServer } = require('ws');

// ---------------------------------------------------------------------------
// Internal modules
// ---------------------------------------------------------------------------

const authMiddleware = require('./middleware/auth');

// ---------------------------------------------------------------------------
// App + HTTP server
// ---------------------------------------------------------------------------

const app    = express();
const server = http.createServer(app);

// ---------------------------------------------------------------------------
// Middleware stack
// ---------------------------------------------------------------------------

// 1. CORS
app.use(
  cors({
    origin: [
      'http://localhost:3000',
      'http://127.0.0.1:3000',
      process.env.FRONTEND_URL
    ].filter(Boolean),
    credentials: true,
  }),
);

// 2. Body parsing
app.use(express.json({ limit: '16kb' }));

// 3. Morgan request logging — stream writes to stdout with [API] prefix
const morganStream = {
  write: (msg) => process.stdout.write(`[API] ${msg}`),
};
app.use(morgan('combined', { stream: morganStream }));

// 4. JWT authentication (skips public paths internally)
app.use(authMiddleware);

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

app.use('/api/auth',    require('./routes/auth'));
app.use('/api/query',   require('./routes/query'));
app.use('/api/metrics', require('./routes/metrics'));
app.use('/api/intents', require('./routes/intents'));
app.use('/api/health',  require('./routes/health'));

// ---------------------------------------------------------------------------
// Internal daemon → WebSocket relay endpoint
// POST /internal-ws-relay  { type: string, ...payload }
// The daemon can POST here to push arbitrary events to all WS clients.
// This endpoint is not JWT-protected (it is internal / loopback-only).
// ---------------------------------------------------------------------------

app.post('/internal-ws-relay', express.json({ limit: '64kb' }), (req, res) => {
  const payload = req.body || {};
  broadcastToClients(payload);
  return res.status(200).json({ relayed: true, clients: connectedClients.size });
});

// ---------------------------------------------------------------------------
// 404 handler
// ---------------------------------------------------------------------------

app.use((req, res) => {
  res.status(404).json({ error: 'Not Found' });
});

// ---------------------------------------------------------------------------
// Global error handler (Express 5 signature requires four params)
// ---------------------------------------------------------------------------

// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  console.error('[ERROR]', err);
  res.status(err.status || 500).json({
    error: err.message || 'Internal Server Error',
  });
});

// ---------------------------------------------------------------------------
// WebSocket server — /stream
// ---------------------------------------------------------------------------

const wss = new WebSocketServer({ server, path: '/stream' });

/** @type {Set<import('ws').WebSocket>} */
const connectedClients = new Set();

/**
 * Broadcast a JSON-serialisable object to every connected WebSocket client.
 *
 * @param {Record<string, unknown>} data
 */
function broadcastToClients(data) {
  const payload = JSON.stringify(data);
  for (const client of connectedClients) {
    // ws.OPEN === 1
    if (client.readyState === 1 /* WebSocket.OPEN */) {
      client.send(payload);
    }
  }
}

wss.on('connection', (ws) => {
  connectedClients.add(ws);
  console.log(`[WS] Client connected. Total: ${connectedClients.size}`);

  // Greet the new client
  ws.send(JSON.stringify({ type: 'connected', message: 'AIOS stream connected' }));

  ws.on('close', () => {
    connectedClients.delete(ws);
    console.log(`[WS] Client disconnected. Total: ${connectedClients.size}`);
  });

  ws.on('error', (err) => {
    console.warn('[WS] Client error:', err.message);
    connectedClients.delete(ws);
  });
});

// ---------------------------------------------------------------------------
// Daemon metrics polling — every 5 seconds
// ---------------------------------------------------------------------------

/** Push daemon metrics into the ring buffer and broadcast to WS clients. */
async function pollDaemonMetrics() {
  try {
    const response = await fetch('http://127.0.0.1:8765/metrics');
    const metrics  = await response.json();

    // Also record in the metrics route's ring buffer so /api/metrics/history
    // reflects polled data even when nobody calls GET /api/metrics directly.
    try {
      const { pushToHistory } = require('./routes/metrics');
      pushToHistory(metrics);
    } catch (_) {
      // Non-critical — ring buffer update failed, carry on.
    }

    if (connectedClients.size > 0) {
      broadcastToClients({ type: 'metrics_update', ...metrics });
    }
  } catch (err) {
    // Daemon is down — log and continue; do NOT crash the API.
    console.warn('[POLL] Daemon unavailable:', err.message);
  }
}

// Start polling after the server is listening (see server.listen callback).
let metricsPoller = null;

// ---------------------------------------------------------------------------
// Start HTTP server
// ---------------------------------------------------------------------------

const PORT = process.env.PORT || 5000;

server.listen(PORT, () => {
  console.log(`[AIOS API] Listening on port ${PORT}`);

  // Begin polling daemon metrics once the server is up.
  metricsPoller = setInterval(pollDaemonMetrics, 5000);
});

// ---------------------------------------------------------------------------
// Graceful shutdown
// ---------------------------------------------------------------------------

function shutdown(signal) {
  console.log(`[AIOS API] Received ${signal} — shutting down…`);

  if (metricsPoller) clearInterval(metricsPoller);

  wss.close(() => {
    server.close(() => {
      console.log('[AIOS API] Server closed.');
      process.exit(0);
    });
  });

  // Force exit after 10 s if graceful shutdown hangs.
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT',  () => shutdown('SIGINT'));

// ---------------------------------------------------------------------------
// Exports (for testing)
// ---------------------------------------------------------------------------

module.exports = { app, server, broadcastToClients, connectedClients };
