# Deploying CineLibre API on Render

## Option 1: Using render.yaml (Recommended)

The `render.yaml` file is already configured. Just connect your GitHub repo to Render and it will automatically use this configuration.

## Option 2: Manual Dashboard Configuration

If you're setting up manually in the Render dashboard, use these settings:

### Basic Settings
- **Name**: cinelibre-api
- **Environment**: Python 3
- **Region**: Oregon (or closest to you)
- **Branch**: main
- **Root Directory**: (leave empty)

### Build & Deploy Settings
- **Build Command**: 
  ```bash
  pip install -r requirements.txt
  ```

- **Start Command**: 
  ```bash
  gunicorn -w 1 -k uvicorn.workers.UvicornWorker api.main:app --bind 0.0.0.0:$PORT --timeout 120
  ```

### Environment Variables
Add these in the Render dashboard:

| Key | Value | Notes |
|-----|-------|-------|
| `PYTHON_VERSION` | `3.13.4` | Python version |
| `SUPABASE_URL` | `your-supabase-url` | From Supabase dashboard |
| `SUPABASE_KEY` | `your-supabase-key` | From Supabase dashboard |
| `TMDB_API_KEY` | `your-tmdb-key` | From TMDB |
| `JWT_SECRET` | `your-secret-key` | Generate a random string |
| `GOOGLE_BOOKS_API_KEY` | `your-books-key` | Optional |

### Advanced Settings
- **Plan**: Free (or Starter if you need more resources)
- **Auto-Deploy**: Yes (deploy on git push)
- **Health Check Path**: `/`

## Important Notes

### 1. Memory Optimization
The app is configured to use minimal memory:
- Single worker (`-w 1`)
- Thread limits set in code
- Model loaded as singleton

### 2. Timeout
Set to 120 seconds to allow for:
- Model loading on first request
- TMDB API calls
- Embedding generation

### 3. Port Binding
Render provides `$PORT` environment variable - the app automatically binds to it.

## Troubleshooting

### Error: "ModuleNotFoundError: No module named 'app'"
**Cause**: Render is using default command `gunicorn app:app`

**Solution**: Update Start Command to:
```bash
gunicorn -w 1 -k uvicorn.workers.UvicornWorker api.main:app --bind 0.0.0.0:$PORT
```

### Error: "Worker timeout"
**Cause**: Model loading takes too long

**Solution**: Increase timeout in Start Command:
```bash
gunicorn -w 1 -k uvicorn.workers.UvicornWorker api.main:app --bind 0.0.0.0:$PORT --timeout 180
```

### Error: "Out of memory"
**Cause**: Free tier has limited RAM

**Solutions**:
1. Ensure using single worker (`-w 1`)
2. Upgrade to Starter plan ($7/month with 512MB RAM)
3. Use Koyeb instead (better free tier for ML apps)

### Health Check Failing
**Cause**: Model loading on first request

**Solution**: 
1. Set health check path to `/`
2. Increase health check timeout to 60 seconds
3. The first request will be slow, subsequent ones will be fast

## Deployment Steps

1. **Push code to GitHub**
   ```bash
   git add .
   git commit -m "Add Render configuration"
   git push origin main
   ```

2. **Create Render Service**
   - Go to https://dashboard.render.com
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Render will detect `render.yaml` automatically

3. **Add Environment Variables**
   - Go to service settings
   - Add all required environment variables
   - Click "Save Changes"

4. **Deploy**
   - Render will automatically deploy
   - Wait for build to complete (~3-5 minutes)
   - Check logs for any errors

5. **Test**
   ```bash
   curl https://your-app.onrender.com/
   ```

## Comparing Render vs Koyeb

| Feature | Render Free | Koyeb Free |
|---------|-------------|------------|
| RAM | 512MB | 512MB |
| CPU | Shared | Shared |
| Sleep after inactivity | Yes (15 min) | No |
| Cold start | ~30s | ~10s |
| Build time | 3-5 min | 2-3 min |
| Custom domains | Yes | Yes |
| Auto-deploy | Yes | Yes |

**Recommendation**: Koyeb is better for ML apps due to:
- No sleep on free tier
- Faster cold starts
- Better for APIs that need to be always available

## Current Deployment

This app is currently deployed on **Koyeb** at:
- URL: https://cinelibre-koyeb-cinelibre.koyeb.app
- Status: Active
- Configuration: Procfile

If you want to switch to Render, follow the steps above.
