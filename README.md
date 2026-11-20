# Quorum Backend

A comprehensive Django REST API for enterprise asset management system with role-based access control, AI-powered insights, and real-time notifications.

## 🚀 Features

### Core Asset Management
- **Asset Inventory**: Track assets by category, location, and status with detailed metadata
- **Asset Units**: Manage individual asset units with serial numbers and barcodes
- **Asset Assignment**: Assign assets to users/departments with tracking and history
- **Asset Depreciation**: Calculate asset value over time with multiple depreciation methods
- **Asset Requests**: Employees can request assets with manager approval workflow

### Financial Management
- **Purchase Tracking**: Record purchases with supplier details and payment tracking
- **Payment Management**: Handle multiple payment methods (bank transfer, cheque, mobile wallet)
- **Invoice Generation**: Automated invoice creation and PDF export
- **Supplier Management**: Maintain supplier database with contact and payment information

### Maintenance & Operations
- **Maintenance Requests**: Create, track, and manage asset maintenance tickets
- **Technician Assignment**: Assign maintenance tasks to technicians with status updates
- **Maintenance History**: Complete audit trail of all maintenance activities
- **Work Updates**: Technicians can provide real-time status updates on repairs

### AI & Automation
- **AI Assistant**: Groq and OpenRouter powered AI for smart asset insights
- **AI-Generated Descriptions**: Automated maintenance issue descriptions
- **Natural Language Processing**: Convert voice/text to actionable maintenance requests

### Notifications & Compliance
- **Push Notifications**: Firebase Cloud Messaging for real-time alerts
- **Notification Preferences**: User-configurable notification settings
- **Audit Logging**: Complete audit trail of all system activities
- **Role-Based Access Control**: Fine-grained permissions system (Admin, Manager, Technician, User)

### User Management
- **User Accounts**: Create and manage user accounts with roles
- **Department Management**: Organize users by departments
- **Employee Profiles**: Track employee information and assignments
- **Permission Management**: Granular control over user capabilities

## 📋 Requirements

- Python 3.10+
- PostgreSQL 12+
- Django 6.0.4
- Django REST Framework 3.17.1

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone https://github.com/umairlabs/quorum-backend.git
cd quorum-backend
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

**Required environment variables:**
```
DEBUG=False
SECRET_KEY=your-django-secret-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/quorum
GROQ_API_KEY=sk-your-groq-api-key
OPENROUTER_API_KEY=sk-your-openrouter-api-key
FIREBASE_CREDENTIALS_PATH=/path/to/service-account.json  # Optional
```

### 5. Database Setup
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 6. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

## 🚀 Running the Server

### Development
```bash
python manage.py runserver
```

### Production
```bash
gunicorn config.wsgi:application
```

The API will be available at `http://localhost:8000/api`

## 📚 API Documentation

### Authentication
All endpoints require JWT token authentication (except login):
```bash
Authorization: Bearer <your_jwt_token>
```

### Key Endpoints

#### Authentication
- `POST /api/auth/login/` - User login
- `POST /api/auth/logout/` - User logout
- `POST /api/auth/refresh/` - Refresh JWT token

#### Assets
- `GET /api/assets/` - List all assets
- `POST /api/assets/` - Create asset
- `GET /api/assets/{id}/` - Get asset details
- `PUT /api/assets/{id}/` - Update asset
- `DELETE /api/assets/{id}/` - Delete asset
- `POST /api/assets/{id}/assign/` - Assign asset to user

#### Asset Assignments
- `GET /api/assignments/` - List assignments
- `POST /api/assignments/` - Create assignment
- `PUT /api/assignments/{id}/` - Update assignment
- `DELETE /api/assignments/{id}/` - Remove assignment

#### Purchases
- `GET /api/purchases/` - List purchases
- `POST /api/purchases/` - Create purchase
- `GET /api/purchases/{id}/` - Get purchase details
- `POST /api/purchases/{id}/payments/` - Record payment

#### Maintenance
- `GET /api/maintenance/` - List maintenance requests
- `POST /api/maintenance/` - Create maintenance request
- `PUT /api/maintenance/{id}/` - Update maintenance status
- `POST /api/maintenance/{id}/updates/` - Add work update

#### Users
- `GET /api/users/` - List users
- `POST /api/users/` - Create user
- `GET /api/users/{id}/` - Get user details
- `PUT /api/users/{id}/` - Update user

#### Audit Logs
- `GET /api/audit-logs/` - View activity logs

#### Depreciation
- `GET /api/depreciation/` - View depreciation schedules

### Pagination
All list endpoints support pagination with `limit` and `offset` parameters:
```
GET /api/assets/?limit=20&offset=0
```

### Filtering & Search
Most list endpoints support filtering:
```
GET /api/assets/?category=Electronics&status=Active
GET /api/users/?department=IT
```

## 🔐 Security

- All credentials are managed via environment variables (no hardcoded secrets)
- Firebase credentials are optional - notifications work without them
- CORS properly configured for frontend domain
- Rate limiting on authentication endpoints
- SQL injection protection via Django ORM
- CSRF protection on forms
- Password hashing with PBKDF2
- JWT token expiration and refresh

**Important**: Before deploying to production:
1. Generate a new Django SECRET_KEY
2. Set DEBUG=False
3. Configure allowed hosts
4. Set up HTTPS
5. Rotate API keys if previously exposed

See `SECURITY.md` for detailed security guidelines.

## 📦 Architecture

### Django Apps
- **authentication**: User authentication and JWT tokens
- **users**: User management and profiles
- **assets**: Asset inventory and assignment
- **purchases**: Purchase orders and payments
- **maintenance**: Maintenance requests and tracking
- **depreciation**: Asset depreciation calculations
- **notifications**: Push notifications and preferences
- **audit**: Activity logging and audit trails
- **ai**: AI assistant integration
- **common**: Shared utilities and helpers

### Database Models
- User, Department, Location
- Asset, AssetCategory, AssetUnit, AssetAssignmentHistory
- Purchase, Payment, Supplier
- MaintenanceRequest, MaintenanceUpdate
- Notification, UserNotificationPreference, FCMDevice
- AuditLog, DepreciationSchedule

### External Integrations
- **Firebase Admin SDK**: Push notifications
- **Groq API**: AI-powered insights
- **OpenRouter API**: Alternative AI provider

## 🧪 Testing

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.assets

# With coverage report
coverage run --source='.' manage.py test
coverage report
```

## 📝 Environment Variables Reference

See `.env.example` for complete list. Key variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key for cryptography | Yes |
| `DEBUG` | Debug mode (False for production) | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `GROQ_API_KEY` | Groq API key for AI features | No |
| `OPENROUTER_API_KEY` | OpenRouter API key for AI | No |
| `FIREBASE_CREDENTIALS_PATH` | Path to Firebase service account JSON | No |

## 🚀 Deployment

### Using Gunicorn + Nginx

```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn --workers 4 --bind 0.0.0.0:8000 config.wsgi:application
```

### Using Docker
```bash
docker build -t quorum-backend .
docker run -p 8000:8000 --env-file .env quorum-backend
```

### Environment-Specific Deployment
- **Development**: `DEBUG=True`, SQLite or local PostgreSQL
- **Staging**: `DEBUG=False`, Staging database, Test API keys
- **Production**: `DEBUG=False`, Production database, Production credentials, HTTPS only

## 📊 Database Schema

### Key Relationships
- User → Department (many-to-one)
- Asset → Category (many-to-one)
- Asset → AssetUnit (one-to-many)
- AssetUnit → User (assignment history)
- Purchase → Supplier (many-to-one)
- MaintenanceRequest → Asset (many-to-one)

## 🔄 API Response Format

### Success Response
```json
{
  "data": { ... },
  "message": "Operation successful",
  "status": 200
}
```

### Error Response
```json
{
  "error": "Error message",
  "details": { ... },
  "status": 400
}
```

## 🆘 Troubleshooting

### Database Connection Issues
```bash
# Check DATABASE_URL format
# Should be: postgresql://user:password@localhost:5432/dbname
```

### Firebase Not Available
```bash
# Firebase is optional. App works without it.
# To disable: leave FIREBASE_CREDENTIALS_PATH unset
```

### AI Features Not Working
```bash
# Ensure GROQ_API_KEY or OPENROUTER_API_KEY is set
# Check API quota and rate limits
```

### Permission Denied Errors
```bash
# Check user role and permissions
# Verify JWT token is valid
# Check CORS configuration
```

## 📚 Documentation

- [Security Guidelines](./SECURITY.md)
- [Deployment Guide](./DEPLOYMENT_GUIDE.md)
- [Security Audit Report](./SECURITY_AUDIT_REPORT.md)

## 🤝 Contributing

1. Create a feature branch from `main`
2. Make your changes
3. Write tests for new features
4. Ensure all tests pass
5. Create a pull request

## 📄 License

This project is proprietary software. All rights reserved.

## 👨‍💻 Author

Umair Zafar - [GitHub](https://github.com/umairlabs)

## 📧 Support

For issues, questions, or feedback, please create an issue on GitHub.

---

**Version**: 1.0.0  
**Last Updated**: November 2026
