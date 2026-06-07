/**
 * api/routes/health.js — Service health aggregator
 *
 * GET /api/health — public endpoint, no auth required
 *
 * Attempts to reach the Python daemon's own /health endpoint within 2 seconds.
 * Aggregates the daemon's sub-service statuses and always returns HTTP 200 so
 * that load balancers / uptime monitors never see a false error from a healthy
 * API node just because a downstream service is degraded.
 */

'use strict';

const express = require('express');
const fetch   = require('node-fetch');

const router = express.Router();

// ---------------------------------------------------------------------------
// GET /api/health
// ---------------------------------------------------------------------------

/**
 * Aggregate health check across the API and the Python daemon.
 *
 * Response shape:
 * {
 *   api:           true,
 *   daemon:        bool,
 *   faiss:         bool,
 *   atlas:         bool,
 *   colab_tunnel:  bool,
 *   local_ollama:  bool,
 *   timestamp:     ISO-8601 string
 * }
 *
 * Always responds with HTTP 200.
 */
router.get('/', async (req, res) => {
  const timestamp = new Date().toISOString();

  // Default: everything daemon-related is DOWN
  const health = {
    api:          true,
    daemon:       false,
    faiss:        false,
    atlas:        false,
    local_ollama: false,
    timestamp,
  };

  try {
    // AbortController gives us a clean 4-second timeout.
    const controller = new AbortController();
    const timeoutId  = setTimeout(() => controller.abort(), 4000);

    let daemonHealth;
    try {
      const response = await fetch('http://127.0.0.1:8765/health', {
        signal: controller.signal,
      });
      daemonHealth = await response.json();
    } finally {
      clearTimeout(timeoutId);
    }

    // Daemon is reachable — pull sub-service statuses from its response.
    health.daemon       = true;
    health.faiss        = Boolean(daemonHealth?.faiss?.ok ?? daemonHealth?.faiss ?? daemonHealth?.faiss_available);
    health.atlas        = Boolean(daemonHealth?.atlas?.ok ?? daemonHealth?.atlas ?? daemonHealth?.atlas_available);
    health.local_ollama = Boolean(daemonHealth?.local_ollama?.ok ?? daemonHealth?.local_ollama ?? daemonHealth?.ollama_available);
  } catch (err) {
    // Daemon unreachable or timed out — all sub-services stay false.
    console.warn('[HEALTH] Daemon unreachable:', err.message);
  }

  return res.status(200).json(health);
});

module.exports = router;
