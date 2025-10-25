# REST API Reference Documentation

## Overview
This document describes the REST API endpoints for the User Management Service v2.1.0.

## Authentication
All API requests require Bearer token authentication via the Authorization header:
```
Authorization: Bearer <token>
```

## Endpoints

### GET /api/v2/users
Retrieves a paginated list of users.

**Parameters:**
- `page` (integer): Page number (default: 1)
- `limit` (integer): Items per page (default: 50, max: 100)
- `sort` (string): Sort field (name, created_at, updated_at)
- `order` (string): Sort order (asc, desc)

**Response:**
```json
{
  "data": [
    {
      "id": "usr_123",
      "name": "John Doe",
      "email": "john@example.com",
      "role": "admin",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 234
  }
}
```

### POST /api/v2/users
Creates a new user account.

**Request Body:**
```json
{
  "name": "string (required)",
  "email": "string (required, unique)",
  "role": "string (admin|user|viewer)",
  "department": "string (optional)"
}
```

**Response:** 201 Created
```json
{
  "id": "usr_456",
  "name": "Jane Smith",
  "email": "jane@example.com",
  "role": "user",
  "created_at": "2024-03-20T14:25:00Z"
}
```

### DELETE /api/v2/users/{id}
Soft deletes a user account.

**Parameters:**
- `id` (string): User ID

**Response:** 204 No Content

## Error Codes
- 400: Bad Request - Invalid parameters
- 401: Unauthorized - Missing or invalid token
- 404: Not Found - Resource doesn't exist
- 429: Too Many Requests - Rate limit exceeded
- 500: Internal Server Error

## Rate Limiting
API requests are limited to 1000 requests per hour per API key.

---
*Last updated: March 2024*
*Author: API Team*