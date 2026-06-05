/**
 * api/middleware/auth.js — JWT verification middleware
 *
 * Verifies Bearer tokens on all routes except those in the skip list.
 * Sets req.user = decoded JWT payload on success.
 */

'use strict';

const jwt = require('jsonwebtoken');

/** Routes that do not require a valid JWT. */
const SKIP_PATHS = ['/api/auth/login', '/api/health', '/api/health/'];

/**
 * Express middleware that enforces JWT authentication.
 *
 * @param {import('express').Request}  req
 * @param {import('express').Response} res
 * @param {import('express').NextFunction} next
 */
function authMiddleware(req, res, next) {
  // Allow public paths through without any token check.
  const isPublic = SKIP_PATHS.some((skip) => req.path.startsWith(skip));
  if (isPublic) {
    return next();
  }

  // Extract the token from the Authorization header.
  const authHeader = req.headers['authorization'] || '';
  const parts = authHeader.split(' ');

  if (parts.length !== 2 || parts[0].toLowerCase() !== 'bearer' || !parts[1]) {
    return res.status(401).json({
      error: 'Unauthorized',
      message: 'No token provided',
    });
  }

  const token = parts[1];

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.user = decoded;
    return next();
  } catch (err) {
    return res.status(401).json({
      error: 'Unauthorized',
      message: 'Invalid or expired token',
    });
  }
}

module.exports = authMiddleware;
