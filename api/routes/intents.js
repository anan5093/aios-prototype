/**
 * api/routes/intents.js — Intent audit log and approval
 *
 * GET /api/intents              — paginated audit log (any authenticated role)
 * PUT /api/intents/:id/approve  — approve a validated intent (operator+)
 */

'use strict';

const express = require('express');
const fetch   = require('node-fetch');

const { requireRole } = require('../middleware/rbac');

const router = express.Router();

/** Base URL of the Python daemon. */
const DAEMON_BASE = 'http://127.0.0.1:8765';

// ---------------------------------------------------------------------------
// GET /api/intents
// ---------------------------------------------------------------------------

/**
 * Return a paginated list of intent audit records from the daemon.
 *
 * Query params: page (default 1), limit (default 20)
 *
 * 200 : daemon response JSON
 * 503 : daemon unavailable
 */
router.get('/', async (req, res, next) => {
  try {
    const { page = 1, limit = 20 } = req.query;

    let data;
    try {
      const url = `${DAEMON_BASE}/intents?page=${encodeURIComponent(page)}&limit=${encodeURIComponent(limit)}`;
      const response = await fetch(url);
      data = await response.json();
    } catch (fetchErr) {
      console.warn('[INTENTS] Daemon unavailable:', fetchErr.message);
      return res.status(503).json({ error: 'Daemon unavailable' });
    }

    return res.status(200).json(data);
  } catch (err) {
    return next(err);
  }
});

// ---------------------------------------------------------------------------
// PUT /api/intents/:id/approve
// ---------------------------------------------------------------------------

/**
 * Approve a pending intent record by forwarding the decision to the daemon.
 *
 * Body   : { approved_by: string }
 * 200    : daemon confirmation JSON
 * 400    : missing approved_by
 * 503    : daemon unavailable
 */
router.put('/:id/approve', requireRole('operator'), async (req, res, next) => {
  try {
    const { id } = req.params;
    const { approved_by } = req.body || {};

    // ------------------------------------------------------------------
    // Input validation
    // ------------------------------------------------------------------
    if (!approved_by || typeof approved_by !== 'string' || approved_by.trim() === '') {
      return res.status(400).json({
        error:   'Bad Request',
        message: '`approved_by` is required.',
      });
    }

    // ------------------------------------------------------------------
    // Forward to daemon
    // ------------------------------------------------------------------
    let daemonResponse;
    try {
      const response = await fetch(`${DAEMON_BASE}/intents/${encodeURIComponent(id)}/approve`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ approved_by: approved_by.trim() }),
      });
      daemonResponse = await response.json();
    } catch (fetchErr) {
      console.warn('[INTENTS] Daemon unavailable during approve:', fetchErr.message);
      return res.status(503).json({ error: 'Daemon unavailable' });
    }

    return res.status(200).json(daemonResponse);
  } catch (err) {
    return next(err);
  }
});

module.exports = router;
