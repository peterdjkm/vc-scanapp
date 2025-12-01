# Visiting Card Scanner - MVP

Minimal viable product for visiting card scanning and contact extraction.

## Features

- 📷 Camera capture or file upload
- 🔍 OCR using Google Vision API
- 🤖 Hybrid parsing (Regex + Gemini LLM fallback)
- 💾 Contact storage (PostgreSQL)
- 📊 Confidence scoring

## Quick Start

### Local Development

1. **Setup environment:**
   ```bash
   cd backend
   source ~/.peterdjkm/PipEnv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Run backend:**
   ```bash
   python app.py
   ```

4. **Access frontend:**
   - Open `http://localhost:5001` in browser
   - Camera works on HTTPS or localhost

### Deployment to Render.io

1. **Push to Git repository:**
   ```bash
   git init
   git add .
   git commit -m "Initial MVP commit"
   git remote add origin <your-git-repo-url>
   git push -u origin main
   ```

2. **Deploy on Render.io:**
   - Connect your Git repository
   - Render will auto-detect `render.yaml`
   - Set environment variables in Render dashboard:
     - `GOOGLE_APPLICATION_CREDENTIALS` (JSON content)
     - `GEMINI_API_KEY`
     - `DATABASE_URL` (auto-set from database service)

3. **Access your app:**
   - Your app will be available at `https://your-app.onrender.com`
   - Camera will work with HTTPS!

## Environment Variables

- `GOOGLE_APPLICATION_CREDENTIALS` - Google Vision API credentials (JSON)
- `GEMINI_API_KEY` - Google Gemini API key
- `DATABASE_URL` - PostgreSQL connection string (auto-set on Render)
- `USE_LLM_FALLBACK` - Enable LLM fallback (default: true)
- `LLM_CONFIDENCE_THRESHOLD` - LLM trigger threshold (default: 0.95)
- `SAVE_TO_DB` - Save to database (default: true)

## Project Structure

```
mvp/
├── backend/
│   ├── app.py              # Flask application
│   ├── config.py           # Configuration
│   ├── requirements.txt    # Python dependencies
│   ├── render.yaml         # Render.io deployment config
│   ├── routes/             # API routes
│   ├── services/           # Business logic
│   ├── models/            # Database models
│   └── utils/             # Utilities
└── frontend/
    ├── index.html         # Main HTML
    ├── app.js             # Frontend logic
    └── styles.css         # Styling
```

## API Endpoints

- `POST /api/process-card` - Process card image
- `GET /api/contacts` - List contacts
- `POST /api/contacts` - Save contact
- `GET /api/stats` - Get statistics
- `GET /api/health` - Health check

## License

MIT



