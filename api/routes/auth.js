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

// ---------------------------------------------------------------------------
// GET /api/auth/admin-status
// ---------------------------------------------------------------------------
router.get('/admin-status', (req, res) => {
  const adminExists = USERS_DB.some((u) => u.role === 'admin');
  return res.status(200).json({ adminExists });
});

// ---------------------------------------------------------------------------
// POST /api/auth/register
// ---------------------------------------------------------------------------
router.post('/register', (req, res) => {
  const { email, password, role, adminVerifyPassword } = req.body || {};

  if (!email || !password || !role) {
    return res.status(400).json({ error: 'Bad Request', message: '`email`, `password`, and `role` are required.' });
  }

  // Check if an admin exists
  const adminExists = USERS_DB.some((u) => u.role === 'admin');

  if (!adminExists) {
    // 1st Registered person becomes admin automatically
    const existing = USERS_DB.find((u) => u.email === email.toLowerCase().trim());
    if (existing) {
      return res.status(400).json({ error: 'Bad Request', message: 'User already exists.' });
    }

    const newUser = {
      email: email.toLowerCase().trim(),
      hash: bcrypt.hashSync(password, 12),
      role: 'admin', // Force admin role for the first user
    };
    USERS_DB.push(newUser);
    return res.status(201).json({
      message: 'No administrator was found. First user registered successfully as System Administrator.',
      user: { email: newUser.email, role: newUser.role }
    });
  }

  // Admin exists, so authorization is required
  const authHeader = req.headers['authorization'] || '';
  const parts = authHeader.split(' ');

  if (parts.length !== 2 || parts[0].toLowerCase() !== 'bearer' || !parts[1]) {
    return res.status(401).json({
      error: 'Unauthorized',
      message: 'Registration requires an active administrator session.',
    });
  }

  const token = parts[1];
  let decoded;
  try {
    decoded = jwt.verify(token, process.env.JWT_SECRET);
  } catch (err) {
    return res.status(401).json({
      error: 'Unauthorized',
      message: 'Invalid or expired administrator session.',
    });
  }

  // Must have admin role
  if (decoded.role !== 'admin') {
    return res.status(403).json({
      error: 'Forbidden',
      message: 'Only administrators can register new operators.',
    });
  }

  // Find the logged-in admin in the database
  const loggedInAdmin = USERS_DB.find((u) => u.email === decoded.sub.toLowerCase().trim());
  if (!loggedInAdmin) {
    return res.status(401).json({
      error: 'Unauthorized',
      message: 'Active administrator account not found.',
    });
  }

  // PAM-style verification: Admin must verify their own password
  if (!adminVerifyPassword) {
    return res.status(400).json({
      error: 'Bad Request',
      message: 'Administrator password verification (PAM check) is required to authorize registration.',
    });
  }

  const matches = bcrypt.compareSync(adminVerifyPassword, loggedInAdmin.hash);
  if (!matches) {
    return res.status(401).json({
      error: 'Unauthorized',
      message: 'Administrator password verification failed (PAM check rejected).',
    });
  }

  // Check if new user already exists
  const existing = USERS_DB.find((u) => u.email === email.toLowerCase().trim());
  if (existing) {
    return res.status(400).json({ error: 'Bad Request', message: 'User already exists.' });
  }

  // Validations passed, register new user
  const newUser = {
    email: email.toLowerCase().trim(),
    hash: bcrypt.hashSync(password, 12),
    role: role,
  };
  USERS_DB.push(newUser);

  return res.status(201).json({
    message: 'User registered successfully by Administrator.',
    user: { email: newUser.email, role: newUser.role }
  });
});

module.exports = router;
