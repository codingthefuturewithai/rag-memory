# User Management Service - Troubleshooting Guide

Quick reference for common issues and their solutions.

## Authentication Failures

**Problem**: Users cannot log in
**Solution**:
- Check JWT token expiration settings
- Verify API key configuration
- Review authentication service logs

## Database Connection Issues

**Problem**: Service cannot connect to user database
**Solution**:
- Verify DATABASE_URL environment variable
- Check PostgreSQL is running on port 5432
- Test connection with `psql` command

## Performance Issues

**Problem**: Slow API response times
**Solution**:
- Check database query performance
- Review connection pool settings
- Enable query caching for frequently accessed data

## Common Error Codes

- `401 Unauthorized`: Invalid or expired token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: User ID does not exist
- `500 Internal Error`: Check service logs
