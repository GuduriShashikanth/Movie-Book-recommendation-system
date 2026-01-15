-- CineLibre Complete Database Schema
-- Run this ONLY for fresh database setup
-- For existing databases, use migrations.sql instead

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ==================== USERS TABLE ====================
CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ==================== MOVIES TABLE ====================
CREATE TABLE IF NOT EXISTS movies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tmdb_id INTEGER UNIQUE NOT NULL,
  title TEXT NOT NULL,
  overview TEXT,
  release_date DATE,
  poster_url TEXT,
  language TEXT,
  director TEXT,
  genres TEXT[],
  "cast" JSONB,
  crew JSONB,
  embedding vector(384),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_movies_tmdb ON movies(tmdb_id);
CREATE INDEX IF NOT EXISTS idx_movies_embedding ON movies USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_movies_language ON movies(language);
CREATE INDEX IF NOT EXISTS idx_movies_director ON movies(director);
CREATE INDEX IF NOT EXISTS idx_movies_genres ON movies USING GIN(genres);

-- ==================== BOOKS TABLE ====================
CREATE TABLE IF NOT EXISTS books (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  google_id TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  authors TEXT,
  description TEXT,
  thumbnail_url TEXT,
  published_date TEXT,
  categories TEXT,
  language TEXT,
  embedding vector(384),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_books_google ON books(google_id);
CREATE INDEX IF NOT EXISTS idx_books_embedding ON books USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_books_language ON books(language);
CREATE INDEX IF NOT EXISTS idx_books_categories ON books(categories);
CREATE INDEX IF NOT EXISTS idx_books_published ON books(published_date);

-- ==================== RATINGS TABLE ====================
CREATE TABLE IF NOT EXISTS ratings (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  item_id UUID NOT NULL,
  item_type TEXT NOT NULL CHECK (item_type IN ('movie', 'book')),
  rating FLOAT NOT NULL CHECK (rating >= 0.5 AND rating <= 5.0),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, item_id, item_type)
);

CREATE INDEX IF NOT EXISTS idx_ratings_user ON ratings(user_id);
CREATE INDEX IF NOT EXISTS idx_ratings_item ON ratings(item_id, item_type);
CREATE INDEX IF NOT EXISTS idx_ratings_created ON ratings(created_at DESC);

-- ==================== INTERACTIONS TABLE ====================
CREATE TABLE IF NOT EXISTS interactions (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  item_id UUID NOT NULL,
  item_type TEXT NOT NULL CHECK (item_type IN ('movie', 'book')),
  interaction_type TEXT NOT NULL CHECK (interaction_type IN ('view', 'click', 'search')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_interactions_item ON interactions(item_id, item_type);
CREATE INDEX IF NOT EXISTS idx_interactions_created ON interactions(created_at DESC);

-- ==================== RPC FUNCTIONS ====================

-- Function: Match Movies (Semantic Search)
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

-- Function: Match Books (Semantic Search)
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

-- Function: Get Popular Items (Based on ratings)
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

-- Function: Collaborative Filtering Recommendations
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

-- Function: Update timestamp on row update
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ratings_updated_at BEFORE UPDATE ON ratings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
