-- Migration: Require collection descriptions
-- Date: 2025-10-13
-- Purpose: Enforce NOT NULL constraint on collections.description to ensure
--          all collections have meaningful descriptions for better organization

-- Step 1: Update any existing collections with NULL descriptions
-- This ensures the NOT NULL constraint won't fail on existing data
UPDATE collections
SET description = 'No description provided'
WHERE description IS NULL OR description = '';

-- Step 2: Add NOT NULL constraint
ALTER TABLE collections
ALTER COLUMN description SET NOT NULL;

-- Step 3: Add check constraint to prevent empty strings
ALTER TABLE collections
ADD CONSTRAINT description_not_empty CHECK (length(trim(description)) > 0);

-- Verify the changes
SELECT
    tablename,
    attname as column_name,
    attnotnull as is_not_null
FROM pg_attribute
JOIN pg_class ON pg_class.oid = pg_attribute.attrelid
WHERE pg_class.relname = 'collections'
  AND attname = 'description';
