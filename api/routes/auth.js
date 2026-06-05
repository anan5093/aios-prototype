/**
 * api/routes/auth.js — Authentication routes
 *
 * POST /api/auth/login — validate credentials, return JWT
 *
 * Three seed users are created at module load time with bcrypt-hashed passwords
 * (saltRounds = 12).  Production deployments should replace these with a real
 * user-store backed by a database.
 */

'use strict';

const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');

const router = express.Router();

// ---------------------------------------------------------------------------
// Seed users — passwords are hashed once at startup (not on every request).
// ---------------------------------------------------------------------------

const SEED_USERS = [
  { email: 'viewer@aios',   password: 'viewer123',   role: 'viewer'   },
  { email: 'operator@aios', password: 'operator123', role: 'operator' },
  { email: 'admin@aios',    password: 'admin123',    role: 'admin'    },
];

/**
 * @type {Array<{ email: string, hash: string, role: string }>}
 * Built once at module load so the startup cost (bcrypt work factor) is paid
 * once rather than on each incoming request.
 */
const USERS_DB = SEED_USERS.map((u) => ({
  email: u.email,
  hash:  bcrypt.hashSync(u.password, 12),
  role:  u.role,
}));

// ---------------------------------------------------------------------------
// POST /api/auth/login
// ---------------------------------------------------------------------------

/**
 * Authenticate with email + password and receive a signed JWT.
 *
 * Body  : { email: string, password: string }
 * 200   : { token: string, role: string, expires_in: number }
 * 400   : missing fields
 * 401   : invalid credentials
 */
router.post('/login', (req, res) => {
  const { email, password } = req.body || {};

  // ------------------------------------------------------------------
  // Input validation
  // ------------------------------------------------------------------
  if (!email || typeof email !== 'string') {
    return res.status(400).json({ error: 'Bad Request', message: '`email` is required.' });
  }
  if (!password || typeof password !== 'string') {
    return res.status(400).json({ error: 'Bad Request', message: '`password` is required.' });
  }

  // ------------------------------------------------------------------
  // Credential lookup
  // ------------------------------------------------------------------
  const user = USERS_DB.find((u) => u.email === email.toLowerCase().trim());

  if (!user) {
    return res.status(401).json({ error: 'Unauthorized', message: 'Invalid credentials.' });
  }

  const passwordMatch = bcrypt.compareSync(password, user.hash);
  if (!passwordMatch) {
    return res.status(401).json({ error: 'Unauthorized', message: 'Invalid credentials.' });
  }

  // ------------------------------------------------------------------
  // Issue JWT
  // ------------------------------------------------------------------
  const EXPIRES_IN_SECONDS = 86400; // 24 h

  const token = jwt.sign(
    { sub: user.email, role: user.role },
    process.env.JWT_SECRET,
    { expiresIn: '24h' },
  );

  console.info(`[AUTH] Successful login: ${user.email} (role=${user.role})`);

  return res.status(200).json({
    token,
    role:       user.role,
    expires_in: EXPIRES_IN_SECONDS,
  });
});

module.exports = router;
