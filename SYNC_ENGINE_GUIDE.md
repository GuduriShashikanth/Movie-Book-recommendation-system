# Data Sync Engine - Enhanced Version

## What's New

The sync engine has been significantly upgraded to fetch much more data:

### Movies (Target: ~10,000)
- **12 Indian languages**: Hindi, Telugu, Tamil, Kannada, Malayalam, Bengali, Marathi, Punjabi, Gujarati, Odia, Assamese, Urdu
- **Multiple strategies**: Recent, Popular, Top Rated, Box Office
- **5 time periods**: 2020-2026, 2015-2019, 2010-2014, 2000-2009, 1990-1999
- **Deduplication**: Automatically removes duplicates
- **Better rate limiting**: Handles TMDB API limits gracefully

### Books (Target: ~5,000)
- **34 categories**: Fiction, Mystery, Science, Biography, Technology, Romance, Fantasy, Poetry, Drama, Horror, Crime, Psychology, Art, Cooking, Travel, Health, Education, and more
- **Multiple languages**: English, Hindi, Spanish, French, German, Italian, Portuguese, Japanese, Chinese, Arabic
- **2 ordering strategies**: Newest and Relevance
- **Deduplication**: Removes duplicate books
- **Additional metadata**: Authors, categories, published date, language

## How to Use

### Option 1: Test First (Recommended)
```bash
python test_sync.py
```
This fetches just 50 movies and 50 books to verify everything works.

### Option 2: Full Sync
```bash
python run_sync.py
```
This will fetch ~10,000 movies and ~5,000 books. Takes 30-60 minutes.

### Option 3: Custom Sync
Edit `api/sync_engine.py` and modify the targets:
```python
# In run_sync() function
movie_candidates = get_indian_movies(total_target=5000)  # Adjust this
book_candidates = get_global_books(total_target=2000)    # Adjust this
```

## What Gets Stored

### Movies Table
- `tmdb_id` - Unique TMDB identifier
- `title` - Movie title
- `overview` - Plot description
- `release_date` - Release date
- `poster_url` - Poster image URL
- `language` - Original language code
- `embedding` - 384-dimensional vector for semantic search

### Books Table
- `google_id` - Unique Google Books identifier
- `title` - Book title
- `authors` - Primary author
- `description` - Book description (truncated to 2000 chars)
- `thumbnail_url` - Cover image URL
- `published_date` - Publication date
- `categories` - Primary category
- `language` - Language code
- `embedding` - 384-dimensional vector for semantic search

## Performance Tips

1. **Run during off-peak hours** - Less API throttling
2. **Stable internet connection** - Avoid interruptions
3. **Monitor progress** - Check logs for status updates
4. **Resume capability** - Uses upsert, so you can re-run safely

## Troubleshooting

### Rate Limiting
If you hit TMDB rate limits, the script will automatically wait and retry.

### Memory Issues
The script processes in batches. If you have memory constraints, reduce the targets:
```python
get_indian_movies(total_target=2000)  # Instead of 10000
get_global_books(total_target=1000)   # Instead of 5000
```

### Database Errors
Check your Supabase connection and ensure the tables exist with proper schemas.

## Current vs New Data

| Type | Current | New Target | Increase |
|------|---------|------------|----------|
| Movies | ~3,000 | ~10,000 | 3.3x |
| Books | ~500 | ~5,000 | 10x |

## Next Steps

After syncing:
1. Check your Supabase dashboard to verify data
2. Test the search API with new content
3. Monitor recommendation quality with more data
4. Consider scheduling regular syncs for new content
