/**
 * api/routes/query.js — Query forwarding to Python daemon
 *
 * POST /api/query — operator/admin only, forwards to daemon IPC
 *
 * The daemon runs at http://localhost:8765 and is expected to accept the
 * forwarded query and stream results back to the client via WebSocket
 * (/stream endpoint on the API server).
 */

'use strict';

const express = require('express');
const fetch   = require('node-fetch');

const { requireRole } = require('../middleware/rbac');

const router = express.Router();

/** Generate a short random hex string (6 chars). */
const randomHex = () => Math.random().toString(16).slice(2, 8);

// ---------------------------------------------------------------------------
// POST /api/query
// ---------------------------------------------------------------------------

/**
 * Accept a natural-language query, assign it a unique ID, forward it to the
 * Python daemon, and immediately return a 202 so the client can subscribe to
 * streaming results via WebSocket.
 *
 * Body  : { query: string }
 * 202   : { query_id, status, message }
 * 400   : missing/empty query
 * 503   : daemon unavailable
 */
router.post('/', requireRole('operator'), async (req, res, next) => {
  try {
    const { query } = req.body || {};

    // ------------------------------------------------------------------
    // Input validation
    // ------------------------------------------------------------------
    if (!query || typeof query !== 'string' || query.trim() === '') {
      return res.status(400).json({
        error:   'Bad Request',
        message: '`query` must be a non-empty string.',
      });
    }

    // ------------------------------------------------------------------
    // Generate a correlation ID
    // ------------------------------------------------------------------
    const query_id = `qry_${Date.now()}_${randomHex()}`;

    // ------------------------------------------------------------------
    // Forward to daemon
    // ------------------------------------------------------------------
    try {
      await fetch('http://127.0.0.1:8765/query', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ query: query.trim(), query_id }),
      });
    } catch (fetchErr) {
      // Daemon is down — tell the client, don't crash.
      console.warn('[QUERY] Daemon unavailable:', fetchErr.message);
      return res.status(503).json({
        error:   'Daemon unavailable',
        message: 'Python AI daemon is not running',
      });
    }

    // ------------------------------------------------------------------
    // Acknowledge acceptance
    // ------------------------------------------------------------------
    return res.status(202).json({
      query_id,
      status:  'streaming',
      message: 'Query accepted, streaming via WebSocket /stream',
    });
  } catch (err) {
    return next(err);
  }
});

module.exports = router;
