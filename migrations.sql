-- CineLibre Database Migrations
-- Run these on EXISTING databases to add new features
-- Skip any that have already been applied

-- ==================== MIGRATION 1: Add Book Fields ====================
-- Adds: authors, published_date, categories, language to books table

ALTER TABLE books 
ADD COLUMN IF NOT EXISTS authors TEXT,
ADD COLUMN IF NOT EXISTS published_date TEXT,
ADD COLUMN IF NOT EXISTS categories TEXT,
ADD COLUMN IF NOT EXISTS language TEXT;

CREATE INDEX IF NOT EXISTS idx_books_language ON books(language);
CREATE INDEX IF NOT EXISTS idx_books_categories ON books(categories);
CREATE INDEX IF NOT EXISTS idx_books_published ON books(published_date);

-- Update match_books function
DROP FUNCTION IF EXISTS match_books(vector, double precision, integer);

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

-- ==================== MIGRATION 2: Fix Recommendations (UUID Support) ====================
-- Changes item_id from BIGINT to UUID in ratings and interactions tables

ALTER TABLE ratings ALTER COLUMN item_id TYPE UUID USING item_id::text::uuid;
ALTER TABLE interactions ALTER COLUMN item_id TYPE UUID USING item_id::text::uuid;

-- Update get_popular_items function
DROP FUNCTION IF EXISTS get_popular_items(integer);

CREATE OR REPLACE FUNCTION get_popular_items(
  item_limit int DEFAULT 20
)
RETURNS TABLE (
  item_id uuid,
  item_type text,
  title text,
  avg_rating float,
  rating_count bigint,
  poster_url text
)
LANGUAGE sql STABLE
AS $$
  WITH movie_ratings AS (
    SELECT 
      r.item_id,
      'movie' as item_type,
      m.title,
      AVG(r.rating) as avg_rating,
      COUNT(*) as rating_count,
      m.poster_url
    FROM ratings r
    JOIN movies m ON r.item_id = m.id
    WHERE r.item_type = 'movie'
    GROUP BY r.item_id, m.title, m.poster_url
    HAVING COUNT(*) >= 1
  ),
  book_ratings AS (
    SELECT 
      r.item_id,
      'book' as item_type,
      b.title,
      AVG(r.rating) as avg_rating,
      COUNT(*) as rating_count,
      b.thumbnail_url as poster_url
    FROM ratings r
    JOIN books b ON r.item_id = b.id
    WHERE r.item_type = 'book'
    GROUP BY r.item_id, b.title, b.thumbnail_url
    HAVING COUNT(*) >= 1
  )
  SELECT * FROM (
    SELECT * FROM movie_ratings
    UNION ALL
    SELECT * FROM book_ratings
  ) combined
  ORDER BY avg_rating DESC, rating_count DESC
  LIMIT item_limit;
$$;

-- Update get_collaborative_recommendations function
DROP FUNCTION IF EXISTS get_collaborative_recommendations(bigint, integer);

CREATE OR REPLACE FUNCTION get_collaborative_recommendations(
  target_user_id bigint,
  recommendation_count int DEFAULT 20
)
RETURNS TABLE (
  item_id uuid,
  item_type text,
  title text,
  predicted_rating float,
  poster_url text
)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
  RETURN QUERY
  WITH user_ratings AS (
    SELECT item_id, item_type, rating
    FROM ratings
    WHERE user_id = target_user_id
  ),
  similar_users AS (
    SELECT 
      r2.user_id,
      COUNT(*) as common_items,
      CORR(r1.rating, r2.rating) as similarity
    FROM ratings r1
    JOIN ratings r2 ON r1.item_id = r2.item_id AND r1.item_type = r2.item_type
    WHERE r1.user_id = target_user_id 
      AND r2.user_id != target_user_id
    GROUP BY r2.user_id
    HAVING COUNT(*) >= 2 AND CORR(r1.rating, r2.rating) > 0.2
    ORDER BY similarity DESC
    LIMIT 50
  ),
  candidate_items AS (
    SELECT 
      r.item_id,
      r.item_type,
      AVG(r.rating * su.similarity) / AVG(su.similarity) as predicted_rating
    FROM ratings r
    JOIN similar_users su ON r.user_id = su.user_id
    WHERE NOT EXISTS (
      SELECT 1 FROM user_ratings ur 
      WHERE ur.item_id = r.item_id AND ur.item_type = r.item_type
    )
    GROUP BY r.item_id, r.item_type
    HAVING AVG(r.rating) >= 3.0
  )
  SELECT 
    ci.item_id,
    ci.item_type,
    COALESCE(m.title, b.title) as title,
    ci.predicted_rating,
    COALESCE(m.poster_url, b.thumbnail_url) as poster_url
  FROM candidate_items ci
  LEFT JOIN movies m ON ci.item_type = 'movie' AND ci.item_id = m.id
  LEFT JOIN books b ON ci.item_type = 'book' AND ci.item_id = b.id
  ORDER BY ci.predicted_rating DESC
  LIMIT recommendation_count;
END;
$$;

-- ==================== MIGRATION 3: Add Cast & Crew to Movies ====================
-- Adds: cast, crew, director, genres to movies table

ALTER TABLE movies 
ADD COLUMN IF NOT EXISTS "cast" JSONB,
ADD COLUMN IF NOT EXISTS crew JSONB,
ADD COLUMN IF NOT EXISTS director TEXT,
ADD COLUMN IF NOT EXISTS genres TEXT[];

CREATE INDEX IF NOT EXISTS idx_movies_director ON movies(director);
CREATE INDEX IF NOT EXISTS idx_movies_genres ON movies USING GIN(genres);

-- Update match_movies function to include new fields
DROP FUNCTION IF EXISTS match_movies(vector, double precision, integer);

CREATE OR REPLACE FUNCTION match_movies(
  query_embedding vector(384),
  match_threshold float,
  match_count int
)
RETURNS TABLE (
  id uuid,
  tmdb_id integer,
  title text,
  overview text,
  release_date date,
  poster_url text,
  language text,
  director text,
  genres text[],
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    id,
    tmdb_id,
    title,
    overview,
    release_date,
    poster_url,
    language,
    director,
    genres,
    1 - (embedding <=> query_embedding) AS similarity
  FROM movies
  WHERE 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT match_count;
$$;

-- ==================== VERIFICATION ====================
-- Check that all migrations were applied successfully

SELECT 
  'books' as table_name,
  column_name, 
  data_type 
FROM information_schema.columns 
WHERE table_name = 'books' 
AND column_name IN ('authors', 'published_date', 'categories', 'language')

UNION ALL

SELECT 
  'movies' as table_name,
  column_name, 
  data_type 
FROM information_schema.columns 
WHERE table_name = 'movies' 
AND column_name IN ('cast', 'crew', 'director', 'genres')

UNION ALL

SELECT 
  'ratings' as table_name,
  column_name, 
  data_type 
FROM information_schema.columns 
WHERE table_name = 'ratings' 
AND column_name = 'item_id';
