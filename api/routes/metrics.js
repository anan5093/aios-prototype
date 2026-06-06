/**
 * api/routes/metrics.js — System metrics proxy
 *
 * GET /api/metrics         — proxies live metrics from the Python daemon
 * GET /api/metrics/history — returns the last 100 captured snapshots
 *
 * An in-memory ring buffer stores up to MAX_HISTORY snapshots so the
 * dashboard can render a short-term trend without a time-series database.
 */

'use strict';

const express = require('express');
const fetch   = require('node-fetch');

const router = express.Router();

// ---------------------------------------------------------------------------
// In-memory ring buffer (max 100 entries)
// ---------------------------------------------------------------------------

const MAX_HISTORY = 100;

/** @type {Array<Record<string, unknown>>} */
const metricsHistory = [];

/**
 * Push a snapshot into the ring buffer, evicting the oldest entry when full.
 *
 * @param {Record<string, unknown>} snapshot
 */
function pushToHistory(snapshot) {
  if (metricsHistory.length >= MAX_HISTORY) {
    metricsHistory.shift(); // remove oldest
  }
  metricsHistory.push({ ...snapshot, _captured_at: new Date().toISOString() });
}

// ---------------------------------------------------------------------------
// GET /api/metrics
// ---------------------------------------------------------------------------

/**
 * Proxy live metrics from the daemon and cache them in the ring buffer.
 *
 * 200 : daemon metrics JSON
 * 503 : daemon unavailable
 */
router.get('/', async (req, res, next) => {
  try {
    let daemonData;

    try {
      const response = await fetch('http://127.0.0.1:8765/metrics');
      daemonData = await response.json();
    } catch (fetchErr) {
      console.warn('[METRICS] Daemon unavailable:', fetchErr.message);
      return res.status(503).json({ error: 'Daemon unavailable' });
    }

    // Store in ring buffer
    pushToHistory(daemonData);

    return res.status(200).json(daemonData);
  } catch (err) {
    return next(err);
  }
});

// ---------------------------------------------------------------------------
// GET /api/metrics/history
// ---------------------------------------------------------------------------

/**
 * Return all cached metric snapshots (up to MAX_HISTORY).
 *
 * 200 : { count: number, history: Array }
 */
router.get('/history', (req, res) => {
  return res.status(200).json({
    count:   metricsHistory.length,
    history: metricsHistory,
  });
});

// Export the history array so server.js can push daemon-polled data into it.
module.exports = router;
module.exports.metricsHistory  = metricsHistory;
module.exports.pushToHistory   = pushToHistory;
