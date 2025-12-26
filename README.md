# Suhan AI - Production Flask App

A professional ChatGPT-style AI chat application built with Flask, featuring user authentication, streaming AI responses, voice input, long-term memory, and Stripe subscriptions.

## Features

- **User Authentication**: Registration/login with SQLite database and password hashing
- **Chat Interface**: ChatGPT-like dark UI with sidebar navigation
- **Streaming AI**: Token-by-token Gemini AI responses
- **Voice Input**: Web Speech API integration
- **Memory System**: Embeddings-based long-term memory per user
- **Subscriptions**: Stripe integration with Free/Pro plans
- **Responsive Design**: Mobile-friendly CSS-only styling

## Tech Stack

- **Backend**: Flask (Python 3.11)
- **Database**: SQLite
- **AI**: Google Gemini API
- **Payments**: Stripe (test mode)
- **Frontend**: Vanilla HTML/CSS/JS
- **Deployment**: Render (free tier compatible)

## Local Development

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set environment variables:
   - `GENAI_API_KEY`: Your Google Gemini API key
   - `FLASK_SECRET_KEY`: Random secret string
   - `STRIPE_SECRET_KEY`: Stripe test secret key
   - `STRIPE_PUBLISHABLE_KEY`: Stripe test publishable key
4. Run: `python app.py`

## Deployment on Render

1. **Connect GitHub Repo**: In Render dashboard, create a new Web Service and link your GitHub repository.

2. **Environment Variables**: Add the following in Render's Environment settings:
   - `GENAI_API_KEY`: Your Google Gemini API key
   - `FLASK_SECRET_KEY`: A secure random string (generate with `openssl rand -hex 32`)
   - `STRIPE_SECRET_KEY`: Your Stripe test secret key
   - `STRIPE_PUBLISHABLE_KEY`: Your Stripe test publishable key
   - `STRIPE_WEBHOOK_SECRET`: (Optional) For webhook verification

3. **Build Settings**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --bind 0.0.0.0:$PORT app:application`

4. **Deploy**: Render will automatically build and deploy on git push.

## Database

The SQLite database (`db/suhan_ai.db`) is auto-created on first run. It includes tables for users, conversations, messages, memories, and usage tracking.

## File Structure

```
app.py                 # Main Flask application
/templates/
  ├── login.html       # Login page
  ├── register.html    # Registration page
  ├── chat.html        # Main chat interface
  └── billing.html     # Subscription plans
/static/
  ├── style.css        # Dark theme styling
  └── chat.js          # Frontend JavaScript
/db/
  └── suhan_ai.db      # SQLite database
requirements.txt       # Python dependencies
Procfile              # Render start command
```

## API Keys Setup

- **Google Gemini**: Get API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
- **Stripe**: Create test account at [Stripe Dashboard](https://dashboard.stripe.com/test/apikeys)

## Usage Limits

- **Free Plan**: 10 messages per day, no long-term memory
- **Pro Plan**: Unlimited messages + memory ($9.99/month via Stripe)

## Security

- Passwords hashed with Werkzeug
- Session-based authentication
- API keys stored as environment variables
- SQLite database with proper foreign keys

## License

MIT License
