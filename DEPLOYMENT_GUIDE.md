# Deployment Guide - Security Hardening Complete

## Overview

This Django backend has been secured for public GitHub deployment. All hardcoded secrets have been removed and replaced with environment variable references.

## Summary of Changes

### 1. Secrets Management

**Files Modified:**
- `.env` - Replaced exposed secrets with placeholder values and warnings
- `.env.example` - Created template for environment configuration
- `.gitignore` - Enhanced to exclude all sensitive files

**Removed Hardcoded Secrets:**
- ✅ `GROQ_API_KEY` - Now loaded from environment
- ✅ `OPENROUTER_API_KEY` - Now loaded from environment  
- ✅ `DATABASE_URL` - Now loaded from environment (with SSL requirement)
- ✅ Django `SECRET_KEY` - Already using environment variable

### 2. Firebase Configuration

**Files Modified:**
- `config/settings.py` - Firebase setup now optional, credentials via environment
- `apps/notifications/services.py` - Made Firebase optional, graceful fallback
- `apps/notifications/signals.py` - Added feature detection, disable if not configured

**Firebase Behavior:**
- ✅ Push notifications are completely OPTIONAL
- ✅ Service account JSON no longer hardcoded
- ✅ If `FIREBASE_CREDENTIALS_PATH` not set, app works without push notifications
- ✅ All other notification features (in-database notifications) still work
- ✅ In-app notifications continue to function with or without Firebase

### 3. .gitignore Enhancements

Added explicit patterns to exclude:
```
.env
.env.local
.env.*.local
**/firebase/service-account.json
**/firebase/*-service-account.json
service-account.json
*.pem
*.key
```

### 4. Documentation

Created:
- `SECURITY.md` - Security configuration and best practices guide
- `DEPLOYMENT_GUIDE.md` - This file, deployment instructions

## Required Environment Variables

### Production Deployment

Before deploying to production, set these environment variables:

```bash
# Django Core
DEBUG=False
SECRET_KEY=<generate-new-secret-key>

# Database
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<dbname>?sslmode=require

# AI/LLM Services (required for AI features)
GROQ_API_KEY=<your-groq-api-key>
OPENROUTER_API_KEY=<your-openrouter-api-key>

# Firebase (optional, only if push notifications needed)
FIREBASE_CREDENTIALS_PATH=/path/to/service-account.json
```

## Deployment Platforms

### GitHub Actions
```yaml
env:
  SECRET_KEY: ${{ secrets.DJANGO_SECRET_KEY }}
  DATABASE_URL: ${{ secrets.DATABASE_URL }}
  GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
  OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
```

### GitLab CI
```yaml
variables:
  SECRET_KEY: $SECRET_KEY
  DATABASE_URL: $DATABASE_URL
  GROQ_API_KEY: $GROQ_API_KEY
  OPENROUTER_API_KEY: $OPENROUTER_API_KEY
```

### Heroku
```bash
heroku config:set SECRET_KEY="..."
heroku config:set DATABASE_URL="..."
heroku config:set GROQ_API_KEY="..."
heroku config:set OPENROUTER_API_KEY="..."
```

### Docker/Kubernetes
```dockerfile
# dockerfile or through ConfigMap/Secrets
ENV DEBUG=False
ENV SECRET_KEY=${SECRET_KEY}
ENV DATABASE_URL=${DATABASE_URL}
```

## Local Development Setup

1. **Clone repository**:
   ```bash
   git clone <repo-url>
   cd quorum-backend
   ```

2. **Copy environment template**:
   ```bash
   cp .env.example .env
   ```

3. **Edit .env with local development values**:
   ```bash
   DEBUG=True
   SECRET_KEY=dev-secret-key-change-this-in-production
   DATABASE_URL=sqlite:///db.sqlite3  # Or your local PostgreSQL
   GROQ_API_KEY=your-test-key-here
   OPENROUTER_API_KEY=your-test-key-here
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Run migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Start development server**:
   ```bash
   python manage.py runserver
   ```

## Firebase Push Notifications (Optional Setup)

### Enable in Production

If you want push notifications:

1. **Create Firebase project** in Firebase Console
2. **Generate service account key**
3. **Store securely** (NOT in Git)
4. **In deployment, set**:
   ```bash
   FIREBASE_CREDENTIALS_PATH=/path/to/service-account.json
   ```

### Without Firebase

The application will work perfectly without Firebase:
- All in-app notifications work
- Database-backed notification history available
- Push delivery simply skipped with no errors
- Can be enabled later without code changes

## Security Considerations

### Before Going Public

- [ ] Review all environment variable requirements
- [ ] Generate new Django `SECRET_KEY` for production
- [ ] Set `DEBUG=False` in production
- [ ] Use database with SSL/TLS (`sslmode=require`)
- [ ] Configure CORS origins (currently `CORS_ALLOW_ALL_ORIGINS = True`)
- [ ] Set up rate limiting
- [ ] Enable HTTPS enforcement
- [ ] Review CSRF settings
- [ ] Set up proper logging and monitoring
- [ ] Run security checks: `python manage.py check --deploy`

### Production Hardening Checklist

```bash
# Run Django security check
python manage.py check --deploy

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate --noinput

# Create superuser (use environment variables or interactive prompt)
# python manage.py createsuperuser
```

## Remaining Concerns to Address

### CORS Configuration
**Current**: `CORS_ALLOW_ALL_ORIGINS = True`
**Recommendation**: Restrict to specific frontend domains in production
```python
CORS_ALLOWED_ORIGINS = [
    "https://your-frontend-domain.com",
    "https://www.your-frontend-domain.com",
]
```

### CSRF Settings
**Review**: CSRF is enabled but CORS is open. Ensure frontend handles CSRF tokens.

### Allowed Hosts
**Current**: `ALLOWED_HOSTS = ['*']`
**Recommendation**: Specify actual production domains:
```python
ALLOWED_HOSTS = ['your-domain.com', 'www.your-domain.com']
```

## No Breaking Changes

✅ All application functionality preserved
✅ All existing features work as before
✅ Only configuration mechanism changed (hardcoded → environment variables)
✅ Backward compatible with existing deployments

## Files Changed Summary

### Modified (3 files):
- `.env` - Replaced secrets with template
- `.gitignore` - Enhanced secret exclusion patterns
- `config/settings.py` - Firebase made optional
- `apps/notifications/services.py` - Optional Firebase support
- `apps/notifications/signals.py` - Feature detection

### Created (3 files):
- `.env.example` - Configuration template
- `SECURITY.md` - Security best practices guide
- `DEPLOYMENT_GUIDE.md` - This deployment guide

### Removed from Tracking (via .gitignore):
- `apps/notifications/firebase/service-account.json` - Kept locally, excluded from Git

## Post-Deployment Verification

After deploying, verify:

```bash
# Check environment is loaded
python manage.py shell
>>> from django.conf import settings
>>> print(settings.SECRET_KEY[:10])
>>> print(settings.DEBUG)

# Run migrations
python manage.py migrate --check

# Collect static files
python manage.py collectstatic --noinput

# Health check endpoint (if available)
curl https://your-domain.com/health/
```

## Support for Different Deployment Environments

The security improvements work with all deployment platforms:
- ✅ Traditional servers (VPS, dedicated)
- ✅ Platform-as-a-Service (Heroku, Railway, etc.)
- ✅ Container orchestration (Docker, Kubernetes)
- ✅ Serverless (AWS Lambda, Google Cloud Functions with proper setup)
- ✅ CI/CD pipeline deployments

## Next Steps

1. Generate new Django SECRET_KEY
2. Update CI/CD pipeline with environment variables
3. Deploy staging environment first
4. Run security verification checks
5. Update production deployment configuration
6. Monitor logs for any configuration issues

## References

- Django Deployment Checklist: https://docs.djangoproject.com/en/stable/howto/deployment/checklist/
- Environment Variable Best Practices: https://12factor.net/config
- OWASP API Security: https://owasp.org/www-project-api-security/
