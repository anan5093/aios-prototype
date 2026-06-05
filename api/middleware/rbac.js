/**
 * api/middleware/rbac.js — Role-based access control middleware factory
 *
 * Usage: router.post('/approve', requireRole('operator'), handler)
 * Role hierarchy: admin > operator > viewer
 */

'use strict';

/** Numeric levels for each role. Higher = more privileged. */
const ROLE_LEVELS = { viewer: 1, operator: 2, admin: 3 };

/**
 * Returns an Express middleware that rejects requests whose authenticated
 * user does not meet the minimum role requirement.
 *
 * @param {'viewer'|'operator'|'admin'} minimumRole - Lowest acceptable role.
 * @returns {import('express').RequestHandler}
 */
function requireRole(minimumRole) {
  return (req, res, next) => {
    const userLevel = ROLE_LEVELS[req.user?.role] || 0;
    const requiredLevel = ROLE_LEVELS[minimumRole] || 99;

    if (userLevel >= requiredLevel) {
      return next();
    }

    return res.status(403).json({
      error: 'Forbidden',
      message: `Requires role '${minimumRole}' or higher. Your role: '${req.user?.role || 'none'}'`,
    });
  };
}

module.exports = { requireRole, ROLE_LEVELS };
