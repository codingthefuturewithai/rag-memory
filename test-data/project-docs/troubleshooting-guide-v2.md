# User Management Service - Troubleshooting Guide (Updated)

Quick reference for common issues and their solutions - UPDATED VERSION with new OAuth solutions.

## Authentication Failures

**Problem**: Users cannot log in
**Updated Solution (v2)**:
- **NEW:** Check OAuth 2.0 token validation
- **NEW:** Verify identity provider integration
- Check JWT token expiration settings (legacy)
- Verify API key configuration
- Review authentication service logs

## Database Connection Issues

**Problem**: Service cannot connect to user database
**Updated Solution (v2)**:
- **NEW:** Use connection pooling with pgbouncer
- **NEW:** Enable SSL/TLS for database connections
- Verify DATABASE_URL environment variable
- Check PostgreSQL is running on port 5432
- Test connection with `psql` command

## Performance Issues

**Problem**: Slow API response times
**Updated Solution (v2)**:
- **NEW:** Implement Redis caching layer
- **NEW:** Use database read replicas
- Check database query performance
- Review connection pool settings
- Enable query caching for frequently accessed data

## Common Error Codes

- `401 Unauthorized`: Invalid or expired token (check OAuth flow)
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: User ID does not exist
- `500 Internal Error`: Check service logs
- **NEW:** `503 Service Unavailable`: Database connection pool exhausted
