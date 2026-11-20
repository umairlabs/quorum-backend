# Security Configuration Guide

This document outlines the security measures taken to prepare this Django backend for public deployment on GitHub.

## Environment Variables

This project uses environment variables for all sensitive configuration. Never commit actual secrets to version control.

### Required Configuration

1. **Copy the template**: 
   ```bash
   cp .env.example .env
   ```

2. **Fill in required secrets**:
   - `SECRET_KEY`: Generate a new Django secret key for production
   - `DATABASE_URL`: Your production PostgreSQL/database connection string
   - `GROQ_API_KEY`: Your Groq API key (optional if using OpenRouter)
   - `OPENROUTER_API_KEY`: Your OpenRouter API key
   - `DEBUG`: Set to `False` in production

### Optional Configuration

- `FIREBASE_CREDENTIALS_PATH`: Path to Firebase service-account.json (optional, for push notifications)

## Firebase Setup (Optional)

Push notifications via Firebase are completely optional and disabled by default.

### To Enable Firebase Notifications:

1. **Obtain credentials**: Get your Firebase service-account.json from Firebase Console
2. **Store securely**: 
   - DO NOT commit service-account.json to version control
   - Store it in your deployment environment via:
     - CI/CD secrets (GitHub Actions, GitLab CI, etc.)
     - Kubernetes secrets
     - Environment variable pointing to credentials location
3. **Set environment variable**:
   ```bash
   export FIREBASE_CREDENTIALS_PATH=/path/to/service-account.json
   ```
4. **Install dependency**:
   ```bash
   pip install firebase-admin
   ```

### If Firebase is Not Configured:
- The application will still work normally
- Push notifications will be silently skipped
- All other notification features (in-app notifications) continue to work

## Removed Files and Features

The following sensitive files have been removed from version control:
- `apps/notifications/firebase/service-account.json` (Firebase credentials)
- Hardcoded API keys from configuration

These files should be regenerated in your deployment environment using CI/CD secrets or secret management services.

## Security Best Practices

1. **Local Development**:
   - Create a `.env` file locally (not tracked by Git)
   - Use dummy/test credentials for development
   - Never use production secrets in local .env

2. **CI/CD Deployment**:
   - Store all secrets in GitHub Secrets / GitLab CI Variables / equivalent
   - Inject secrets as environment variables during build/deploy
   - Use short-lived or rotatable credentials when possible

3. **Production**:
   - Use managed secret services (AWS Secrets Manager, HashiCorp Vault, etc.)
   - Rotate credentials regularly
   - Monitor for unauthorized access
   - Enable audit logging for credential access

## Gitignore Configuration

The `.gitignore` file now explicitly excludes:
- `.env` and `.env.local` files
- Firebase service account JSON files
- Private keys (`.pem`, `.key`)
- Python caches and virtual environments

## Testing

When running tests with environment variables:
```bash
GROQ_API_KEY=test-key-for-testing python manage.py test
```

## Deployment Checklist

- [ ] Set `DEBUG = False` in production
- [ ] Generate a new `SECRET_KEY` for production
- [ ] Configure database connection with SSL/TLS (`sslmode=require`)
- [ ] Set up all required API keys in environment variables
- [ ] (Optional) Configure Firebase if push notifications are needed
- [ ] Run `python manage.py collectstatic` for static files
- [ ] Run `python manage.py migrate` to apply database migrations
- [ ] Set up proper logging and monitoring
- [ ] Enable HTTPS and CSRF protection
- [ ] Configure CORS origins appropriately (currently set to allow all origins)
- [ ] Set up rate limiting and authentication

## Support for Firebase Migration

If you later decide to move away from Firebase:
1. The core notification system uses the `Notification` model which is database-backed
2. Push delivery via Firebase is optional and can be disabled by not setting `FIREBASE_CREDENTIALS_PATH`
3. All other notification features will continue to work without Firebase
4. Consider alternative push notification services (OneSignal, Pusher, etc.) as drop-in replacements

## References

- [Django Security Documentation](https://docs.djangoproject.com/en/stable/topics/security/)
- [12 Factor App - Configuration](https://12factor.net/config)
- [OWASP API Security](https://owasp.org/www-project-api-security/)
