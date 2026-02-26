# AI Recipe Hub

A Django‑based application for managing and sharing recipes with built‑in Google Gemini AI features.

**Stack:**
- Django LTS (4.2.x)
- Django templates + Bootstrap 5 for UI
- PostgreSQL (with SQLite fallback)
- Google Gemini (`google-generativeai` SDK) for AI services
- Docker / docker-compose for local development
- Production configuration ready (Render/Railway, etc.)

## Project Structure

```
manage.py
requirements.txt
Dockerfile
docker-compose.yml
.env
config/               # Django project configuration
    settings/         # settings package (base, dev, prod)
    urls.py
    wsgi.py
    asgi.py
accounts/              # authentication app
recipes/               # main recipe management app
services/              # AI integration (Gemini service)
templates/             # shared templates
static/                # optional static assets
```

Apps:
- **accounts** – user signup/login/profile, public profiles.
- **recipes** – CRUD, search, sharing, AI features, favorites.
- **services** – encapsulates Google Gemini API calls.

## Features

1. **Recipe management** with full CRUD, ownership restrictions, favorites, status tracking, and public/private visibility.
2. **Search & filters** by keywords, ingredients, cuisine, preparation time.
3. **Sharing system** – public recipes visible to everyone, "copy to my collection" for others.
4. **AI enhancements** via Google Gemini:
   - Generate recipes from available ingredients.
   - Suggest ingredient substitutions.
   - Estimate nutrition (calories/macros).
   - Smart recipe recommendations based on favorites.
5. **Responsive UI** using Bootstrap 5; dashboard, cards, forms, and modals.
6. **Dockerized development** with PostgreSQL service.

## Environment Variables
The app uses `django-environ` to load `.env` and `dj-database-url` to parse `DATABASE_URL`.

## AI Integration Design

All Gemini interactions are encapsulated in `services/gemini_service.py`. This module:

- Reads `GEMINI_API_KEY` from the environment.
- Configures `google.generativeai` once per request.
- Defines helper methods for each AI feature.
- Handles API errors gracefully by raising `GeminiServiceError`.
- Uses a short timeout (20s) to avoid hanging requests.

Views call these helpers and display results via Django's messages framework or session storage. Results are parsed as strict JSON to ensure safety.

## Local Development

### Prerequisites

- Docker & docker-compose (or Python 3.11+ and PostgreSQL locally).

### Using Docker

```sh
# build and start services
docker-compose up --build

# load environment variables
cp .env        # edit the values

# application will be available at http://localhost:8000
```

The `web` service runs migrations automatically on startup; create a superuser with
`docker-compose run web python manage.py createsuperuser`.

### Without Docker

1. Create and activate a virtualenv.
2. `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and adjust.
4. Run `python manage.py migrate`.
5. `python manage.py runserver`

## Deployment Guide

### Render / Railway / Heroku

- Set `DJANGO_SETTINGS_MODULE=config.settings.prod` via environment.
- Provision a PostgreSQL add‑on or service.
- Add `GEMINI_API_KEY`, `SECRET_KEY`, `ALLOWED_HOSTS` appropriately.
- Configure SSL; the prod settings enforce security: HSTS, secure cookies, SSL redirect.

### Static files

Collect static files with:

```sh
python manage.py collectstatic --noinput
```

WhiteNoise is configured for serving static assets in production.

## Additional Notes

- The `google-generativeai` package currently triggers a `FutureWarning` about deprecation; you can switch to `google.genai` when available.
- The code uses class-based views, Django forms, pagination, and messages for a clean architecture.
- Tests are intentionally minimal (stubs) – extend them according to your needs.

## Next Steps

- Add automated tests covering models, views, and the Gemini service.
- Enhance UI (modals, mobile design).
- Implement user preferences for AI recommendations.
- Monitor API usage and handle quota/limits.

Enjoy building your AI-powered recipe hub! 🍽️
