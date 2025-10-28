# Authentication Policy Update - October 2025

## BREAKING CHANGE: JWT Authentication Deprecated

**Effective Date:** October 28, 2025

As of this date, JWT token authentication is **officially deprecated** and will be removed in the next major release.

## Authentication Failures - New Resolution

**Problem**: Users cannot log in

**Current Solution (October 2025)**:
- OAuth 2.0 is now the **ONLY supported authentication method**
- JWT tokens are **no longer accepted** for new sessions
- All authentication must use OAuth 2.0 identity provider integration
- Legacy JWT tokens will expire and cannot be renewed

**What Changed:**
- **REMOVED:** JWT token expiration settings (no longer relevant)
- **REMOVED:** API key configuration (replaced by OAuth client credentials)
- **NEW:** OAuth 2.0 token validation is mandatory
- **NEW:** Identity provider integration required for all authentication

## Migration Required

All services must migrate from JWT to OAuth 2.0 by December 2025. JWT authentication support will be completely removed in version 3.0.
