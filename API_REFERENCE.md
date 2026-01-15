# CineLibre API Reference

**Base URL**: `https://amateur-meredithe-shashikanth-45dbe15b.koyeb.app`

**Version**: 2.0.0

## Table of Contents
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Health Check](#health-check)
  - [Auth Endpoints](#auth-endpoints)
  - [Search](#search)
  - [Ratings](#ratings)
  - [Recommendations](#recommendations)
  - [Movies & Books](#movies--books)
  - [Interactions](#interactions)
- [Data Models](#data-models)
- [Error Handling](#error-handling)

---

## Authentication

Most endpoints require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

Tokens are obtained from `/auth/register` or `/auth/login` endpoints.

---

## Endpoints

### Health Check

#### `GET /`
Check API health and trigger model loading.

**Authentication**: Not required

**Response**:
```json
{
  "status": "online",
  "engine": "FastEmbed",
  "ready": true,
  "database": "connected",
  "version": "2.0.0"
}
```

---

## Auth Endpoints

### Register User

#### `POST /auth/register`
Create a new user account.

**Authentication**: Not required

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "name": "John Doe"
}
```

**Response** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe",
    "created_at": "2026-01-14T10:30:00Z"
  }
}
```

**Errors**:
- `400`: Email already exists
- `422`: Validation error (invalid email format, weak password)

---

### Login

#### `POST /auth/login`
Authenticate existing user.

**Authentication**: Not required

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe",
    "created_at": "2026-01-14T10:30:00Z"
  }
}
```

**Errors**:
- `401`: Invalid credentials
- `404`: User not found

---

### Get Current User

#### `GET /auth/me`
Get authenticated user's profile.

**Authentication**: Required

**Response** (200):
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "John Doe",
  "created_at": "2026-01-14T10:30:00Z"
}
```

---

## Search

### Semantic Search

#### `GET /search/semantic`
Search for movies or books using semantic similarity.

**Authentication**: Required

**Query Parameters**:
- `q` (required): Search query (min 3 characters)
- `item_type` (optional): "movie" or "book" (default: "movie")
- `limit` (optional): Number of results (default: 10, max: 50)

**Example Request**:
```
GET /search/semantic?q=action thriller&item_type=movie&limit=5
```

**Response** (200):
```json
{
  "query": "action thriller",
  "results": [
    {
      "id": "ff0b9d75-3b2f-403a-ab5b-1f18ab5e108f",
      "tmdb_id": 1479090,
      "title": "Edagaiye Apaghatakke Karana",
      "overview": "Dark Comedy Suspense Thriller",
      "release_date": "2025-06-13",
      "poster_url": "https://image.tmdb.org/t/p/w500/cMQPSIZdFmdbLTI97eWsEkpSsZ5.jpg",
      "language": "kn",
      "similarity": 0.658
    }
  ]
}
```

**Book Search Response**:
```json
{
  "query": "mystery novel",
  "results": [
    {
      "id": "abc123-uuid",
      "google_id": "abc123",
      "title": "The Mystery of the Blue Train",
      "authors": "Agatha Christie",
      "description": "A classic mystery novel...",
      "thumbnail_url": "https://books.google.com/...",
      "published_date": "1928",
      "categories": "Fiction",
      "language": "en",
      "similarity": 0.742
    }
  ]
}
```

---

## Ratings

### Create/Update Rating

#### `POST /ratings`
Rate a movie or book.

**Authentication**: Required

**Request Body**:
```json
{
  "item_id": "ff0b9d75-3b2f-403a-ab5b-1f18ab5e108f",
  "item_type": "movie",
  "rating": 4.5
}
```

**Validation**:
- `rating`: Must be between 0.5 and 5.0 (increments of 0.5)
- `item_type`: Must be "movie" or "book"

**Response** (200):
```json
{
  "id": 1,
  "user_id": 1,
  "item_id": "ff0b9d75-3b2f-403a-ab5b-1f18ab5e108f",
  "item_type": "movie",
  "rating": 4.5,
  "created_at": "2026-01-14T10:30:00Z"
}
```

---

### Get My Ratings

#### `GET /ratings/my`
Get all ratings by the authenticated user.

**Authentication**: Required

**Query Parameters**:
- `item_type` (optional): Filter by "movie" or "book"

**Response** (200):
```json
[
  {
    "id": 1,
    "user_id": 1,
    "item_id": "ff0b9d75-3b2f-403a-ab5b-1f18ab5e108f",
    "item_type": "movie",
    "rating": 4.5,
    "created_at": "2026-01-14T10:30:00Z"
  }
]
```

---

### Delete Rating

#### `DELETE /ratings/{rating_id}`
Delete a rating.

**Authentication**: Required

**Response** (200):
```json
{
  "message": "Rating deleted"
}
```

---

## Recommendations

### Personalized Recommendations

#### `GET /recommendations/personalized`
Get personalized recommendations based on user's ratings and behavior.

**Authentication**: Required

**Query Parameters**:
- `limit` (optional): Number of recommendations (default: 20)

**Response** (200):
```json
{
  "popular_items": [
    {
      "item_id": "abc-uuid",
      "item_type": "movie",
      "title": "Movie Title",
      "predicted_rating": 4.2,
      "poster_url": "https://..."
    }
  ],
  "method": "collaborative_filtering"
}
```

**Methods**:
- `collaborative_filtering`: Based on similar users (requires 3+ ratings)
- `popularity_based`: Fallback when insufficient data

---

### Similar Items

#### `GET /recommendations/similar/{item_type}/{item_id}`
Get items similar to a specific movie or book.

**Authentication**: Required

**Path Parameters**:
- `item_type`: "movie" or "book"
- `item_id`: UUID of the item

**Query Parameters**:
- `limit` (optional): Number of results (default: 10)

**Response** (200):
```json
{
  "item_id": "ff0b9d75-3b2f-403a-ab5b-1f18ab5e108f",
  "similar_items": [
    {
      "id": "xyz-uuid",
      "tmdb_id": 123456,
      "title": "Similar Movie",
      "overview": "Description...",
      "release_date": "2024-01-01",
      "poster_url": "https://...",
      "language": "en",
      "similarity": 0.85
    }
  ],
  "method": "content_based"
}
```

---

### Popular Items

#### `GET /recommendations/popular`
Get popular items based on ratings.

**Authentication**: Required

**Query Parameters**:
- `limit` (optional): Number of results (default: 20)

**Response** (200):
```json
{
  "popular_items": [
    {
      "item_id": "abc-uuid",
      "item_type": "movie",
      "title": "Popular Movie",
      "avg_rating": 4.5,
      "rating_count": 150,
      "poster_url": "https://..."
    }
  ],
  "method": "popularity_based"
}
```

---

## Movies & Books

### Get Movie Details

#### `GET /movies/{movie_id}`
Get detailed information about a specific movie.

**Authentication**: Not required

**Query Parameters**:
- `include_details` (optional): If `true`, fetches cast, crew, and genres from TMDB (default: `false`)

**Response** (200) - Basic:
```json
{
  "id": "ff0b9d75-3b2f-403a-ab5b-1f18ab5e108f",
  "tmdb_id": 1479090,
  "title": "Movie Title",
  "overview": "Movie description...",
  "release_date": "2025-06-13",
  "poster_url": "https://image.tmdb.org/t/p/w500/...",
  "language": "en",
  "created_at": "2026-01-11T06:56:55Z"
}
```

**Response** (200) - With Details (`include_details=true`):
```json
{
  "id": "ff0b9d75-3b2f-403a-ab5b-1f18ab5e108f",
  "tmdb_id": 1479090,
  "title": "Movie Title",
  "overview": "Movie description...",
  "release_date": "2025-06-13",
  "poster_url": "https://image.tmdb.org/t/p/w500/...",
  "language": "en",
  "genres": ["Action", "Thriller", "Drama"],
  "cast": [
    {
      "name": "Actor Name",
      "character": "Character Name",
      "profile_path": "https://image.tmdb.org/t/p/w185/..."
    }
  ],
  "crew": {
    "directors": ["Director Name"],
    "writers": ["Writer Name"],
    "producers": ["Producer Name"]
  },
  "runtime": 120,
  "budget": 50000000,
  "revenue": 150000000,
  "vote_average": 7.5,
  "vote_count": 1234,
  "created_at": "2026-01-11T06:56:55Z"
}
```

**Example Requests**:
```
GET /movies/ff0b9d75-3b2f-403a-ab5b-1f18ab5e108f
GET /movies/ff0b9d75-3b2f-403a-ab5b-1f18ab5e108f?include_details=true
```

---

### Get Book Details

#### `GET /books/{book_id}`
Get detailed information about a specific book.

**Authentication**: Not required

**Response** (200):
```json
{
  "id": "abc-uuid",
  "google_id": "abc123",
  "title": "Book Title",
  "authors": "Author Name",
  "description": "Book description...",
  "thumbnail_url": "https://books.google.com/...",
  "published_date": "2020",
  "categories": "Fiction",
  "language": "en",
  "created_at": "2026-01-11T06:44:01Z"
}
```

---

### List Movies

#### `GET /movies`
List movies with pagination.

**Authentication**: Not required

**Query Parameters**:
- `skip` (optional): Number of items to skip (default: 0)
- `limit` (optional): Number of items to return (default: 20, max: 100)

**Response** (200):
```json
{
  "movies": [
    {
      "id": "uuid",
      "tmdb_id": 123456,
      "title": "Movie Title",
      "overview": "Description...",
      "release_date": "2024-01-01",
      "poster_url": "https://...",
      "language": "en",
      "created_at": "2026-01-11T06:56:55Z"
    }
  ],
  "skip": 0,
  "limit": 20
}
```

---

## Interactions

### Track Interaction

#### `POST /interactions`
Track user interactions for analytics and recommendations.

**Authentication**: Required

**Request Body**:
```json
{
  "item_id": "ff0b9d75-3b2f-403a-ab5b-1f18ab5e108f",
  "item_type": "movie",
  "interaction_type": "view"
}
```

**Interaction Types**:
- `view`: User viewed item details
- `click`: User clicked on item
- `search`: Item appeared in search results

**Response** (200):
```json
{
  "message": "Interaction tracked"
}
```

---

## Data Models

### User
```typescript
{
  id: number
  email: string
  name: string
  created_at: string (ISO 8601)
}
```

### Movie
```typescript
{
  id: string (UUID)
  tmdb_id: number
  title: string
  overview: string
  release_date: string (YYYY-MM-DD)
  poster_url: string | null
  language: string
  created_at: string (ISO 8601)
}
```

### Book
```typescript
{
  id: string (UUID)
  google_id: string
  title: string
  authors: string | null
  description: string
  thumbnail_url: string | null
  published_date: string | null
  categories: string | null
  language: string | null
  created_at: string (ISO 8601)
}
```

### Rating
```typescript
{
  id: number
  user_id: number
  item_id: string (UUID)
  item_type: "movie" | "book"
  rating: number (0.5 - 5.0)
  created_at: string (ISO 8601)
}
```

---

## Error Handling

### Standard Error Response
```json
{
  "detail": "Error message description"
}
```

### HTTP Status Codes
- `200`: Success
- `400`: Bad Request (validation error)
- `401`: Unauthorized (missing or invalid token)
- `404`: Not Found
- `422`: Unprocessable Entity (validation error)
- `500`: Internal Server Error

### Common Errors

**Authentication Error**:
```json
{
  "detail": "Invalid authentication credentials"
}
```

**Validation Error**:
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## Rate Limiting

Currently no rate limiting is enforced, but please be respectful:
- Max 100 requests per minute per user
- Search queries: Max 10 per minute
- Batch operations: Use pagination

---

## CORS

CORS is enabled for all origins. In production, this should be restricted to your frontend domain.

---

## Best Practices

1. **Cache tokens**: Store JWT tokens securely (localStorage/sessionStorage)
2. **Handle errors**: Always check response status codes
3. **Pagination**: Use skip/limit for large datasets
4. **Debounce search**: Wait 300ms after user stops typing
5. **Optimize images**: Use poster URLs with appropriate sizes
6. **Track interactions**: Call `/interactions` for better recommendations

---

## Example Usage (JavaScript)

```javascript
// Register user
const register = async (email, password, name) => {
  const response = await fetch('https://amateur-meredithe-shashikanth-45dbe15b.koyeb.app/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name })
  });
  const data = await response.json();
  localStorage.setItem('token', data.access_token);
  return data;
};

// Search movies
const searchMovies = async (query) => {
  const token = localStorage.getItem('token');
  const response = await fetch(
    `https://amateur-meredithe-shashikanth-45dbe15b.koyeb.app/search/semantic?q=${encodeURIComponent(query)}&item_type=movie&limit=10`,
    {
      headers: { 'Authorization': `Bearer ${token}` }
    }
  );
  return await response.json();
};

// Rate movie
const rateMovie = async (itemId, rating) => {
  const token = localStorage.getItem('token');
  const response = await fetch('https://amateur-meredithe-shashikanth-45dbe15b.koyeb.app/ratings', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      item_id: itemId,
      item_type: 'movie',
      rating: rating
    })
  });
  return await response.json();
};
```

---

## Support

For issues or questions:
- GitHub: [Movie-Book-recommendation-system](https://github.com/GuduriShashikanth/Movie-Book-recommendation-system)
- Email: support@cinelibre.com (if available)
