-- Migration: Add additional fields to books table
-- Run this in your Supabase SQL Editor

-- Add new columns to books table
ALTER TABLE books 
ADD COLUMN IF NOT EXISTS authors TEXT,
ADD COLUMN IF NOT EXISTS published_date TEXT,
ADD COLUMN IF NOT EXISTS categories TEXT,
ADD COLUMN IF NOT EXISTS language TEXT;

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_books_language ON books(language);
CREATE INDEX IF NOT EXISTS idx_books_categories ON books(categories);
CREATE INDEX IF NOT EXISTS idx_books_published ON books(published_date);

-- Drop the old function first
DROP FUNCTION IF EXISTS match_books(vector, double precision, integer);

-- Recreate the match_books function with new fields (using uuid for id)
CREATE OR REPLACE FUNCTION match_books(
  query_embedding vector(384),
  match_threshold float,
  match_count int
)
RETURNS TABLE (
  id uuid,
  google_id text,
  title text,
  authors text,
  description text,
  thumbnail_url text,
  published_date text,
  categories text,
  language text,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    id,
    google_id,
    title,
    authors,
    description,
    thumbnail_url,
    published_date,
    categories,
    language,
    1 - (embedding <=> query_embedding) AS similarity
  FROM books
  WHERE 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT match_count;
$$;

-- Verify the changes
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'books' 
ORDER BY ordinal_position;
