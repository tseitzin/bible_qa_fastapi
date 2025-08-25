# Heroku Deployment Guide

## Quick Deploy Steps

1. **Create Heroku App:**
   ```bash
   heroku create your-bible-qa-api
   ```

2. **Add PostgreSQL:**
   ```bash
   heroku addons:create heroku-postgresql:essential-0
   ```

3. **Set Environment Variables:**
   ```bash
   heroku config:set OPENAI_API_KEY=your_openai_api_key_here
   heroku config:set ALLOWED_ORIGINS=https://your-vue-app.netlify.app,http://localhost:5173
   heroku config:set DEBUG=false
   ```

4. **Deploy:**
   ```bash
   git add .
   git commit -m "Configure for Heroku deployment"
   git push heroku main
   ```

## Frontend Integration

### Vue.js Configuration

Update your Vue.js app to connect to the Heroku API:

```javascript
// api/config.js
export const API_CONFIG = {
  baseURL: process.env.NODE_ENV === 'production' 
    ? 'https://your-bible-qa-api.herokuapp.com'
    : 'http://localhost:8000',
  timeout: 10000
};

// api/bible.js
import axios from 'axios';
import { API_CONFIG } from './config';

const api = axios.create(API_CONFIG);

export const bibleAPI = {
  async askQuestion(question, userId = 1) {
    const response = await api.post('/api/ask', {
      question,
      user_id: userId
    });
    return response.data;
  },

  async getHistory(userId, limit = 10) {
    const response = await api.get(`/api/history/${userId}?limit=${limit}`);
    return response.data;
  },

  async healthCheck() {
    const response = await api.get('/');
    return response.data;
  }
};
```

### Environment Variables for Vue.js

Create `.env.production` in your Vue.js project:

```bash
# .env.production
VITE_API_BASE_URL=https://your-bible-qa-api.herokuapp.com
```

## CORS Configuration

Make sure to update the `ALLOWED_ORIGINS` environment variable on Heroku to include your Vue.js app's URL:

```bash
# For Netlify deployment
heroku config:set ALLOWED_ORIGINS=https://your-vue-app.netlify.app,http://localhost:5173

# For Vercel deployment  
heroku config:set ALLOWED_ORIGINS=https://your-vue-app.vercel.app,http://localhost:5173

# For multiple deployments
heroku config:set ALLOWED_ORIGINS=https://your-vue-app.netlify.app,https://your-vue-app.vercel.app,http://localhost:5173
```

## Monitoring and Logs

```bash
# View logs
heroku logs --tail

# Check app status
heroku ps

# Open app in browser
heroku open

# Check database
heroku pg:info
```

## Scaling

```bash
# Scale web dynos
heroku ps:scale web=1

# Upgrade database (if needed)
heroku addons:upgrade heroku-postgresql:standard-0
```

## Troubleshooting

1. **Database Connection Issues:**
   ```bash
   heroku config:get DATABASE_URL
   heroku pg:reset DATABASE_URL --confirm your-app-name
   ```

2. **CORS Issues:**
   - Verify `ALLOWED_ORIGINS` includes your frontend URL
   - Check browser developer tools for CORS errors

3. **OpenAI API Issues:**
   - Verify `OPENAI_API_KEY` is set correctly
   - Check OpenAI API usage limits

4. **Build Issues:**
   ```bash
   heroku buildpacks:clear
   heroku buildpacks:add heroku/python
   ```