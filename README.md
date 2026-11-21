# Quorum - Enterprise Asset Management System

An intelligent, enterprise-grade asset management platform designed to help organizations efficiently track, assign, maintain, and manage their valuable IT assets and equipment. From tracking expensive servers and laptops to managing asset depreciation and maintenance workflows, Quorum provides a comprehensive solution with real-time notifications, AI-powered assistance, and detailed audit trails.

![Django](https://img.shields.io/badge/Django-6.0.4-092E20?style=flat-square&logo=django)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?style=flat-square&logo=postgresql)
![Angular](https://img.shields.io/badge/Angular-20.3.25-DD0031?style=flat-square&logo=angular)
![Ionic](https://img.shields.io/badge/Ionic-8.0.0-3880FF?style=flat-square&logo=ionic)
![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Running the Backend](#running-the-backend)
- [Project Structure](#project-structure)
- [API Documentation](#api-documentation)
- [Core Modules](#core-modules)
- [Authentication & Authorization](#authentication--authorization)
- [Environment Variables](#environment-variables)
- [Deployment](#deployment)
- [Security](#security)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

## Features

### 🏢 Asset Management
- **Comprehensive Asset Tracking**: Track IT assets including laptops, servers, desktops, and other equipment
- **SKU & Serial Number Management**: Unique identifiers for every asset unit for complete traceability
- **Asset Categories**: Organize assets into logical categories with auto-icon detection
- **Warranty Tracking**: Monitor warranty periods with expiration alerts
- **Financial Tracking**: Track purchase costs, current value, and depreciation
- **Multi-unit Assets**: Support for multiple units of the same asset model

### 👥 Asset Assignment & Employee Management
- **Employee Asset Assignment**: Assign assets to employees with expected return dates
- **Assignment History**: Complete audit trail of all asset movements
- **Return Management**: Track asset condition on return with receipt confirmation
- **Department Tracking**: Organize employees and assets by department
- **Role-Based Access**: Four built-in roles with customizable permissions

### 🔧 Maintenance Management
- **Maintenance Request Lifecycle**: From request to completion with verified status
- **Multiple Maintenance Types**: Preventive, Corrective, Emergency, Inspection, Upgrade
- **Priority Management**: Low, Medium, High, and Critical priority levels
- **Technician Assignment**: Assign maintenance requests to external technicians
- **Timeline Tracking**: Complete history of all status changes and work done
- **Notes & Documentation**: Detailed notes from technicians and requesters

### 💰 Financial & Depreciation
- **Automatic Depreciation Calculation**: Straight-line and other depreciation methods
- **Salvage Value Tracking**: Define and track asset salvage value
- **Useful Life Management**: Configure asset useful life in years
- **Current Value Updates**: Real-time asset valuation for financial reporting
- **Financial Reporting**: Generate depreciation and asset value reports

### 📊 Reporting & Analytics
- **Dashboard Overview**: Key metrics and summaries at a glance
- **Date Range Filtering**: Analyze data across custom date ranges
- **Real-time Statistics**: Up-to-date asset and maintenance metrics
- **Permission-Based Visibility**: Users see only data relevant to their role
- **Export Capabilities**: Generate reports for financial and operational analysis

### 🔔 Real-time Notifications
- **Multi-Type Notifications**: Maintenance, Asset, Assignment, Warranty, and System alerts
- **Firebase Push Notifications**: Optional push notifications to mobile devices (FCM)
- **In-App Notifications**: Database-backed notification history
- **User Preferences**: Granular notification preference controls
- **Device Token Management**: Automatic FCM device token tracking

### 🤖 AI Assistance
- **Intelligent Issue Generation**: AI-powered maintenance issue descriptions
- **Natural Language Processing**: Assist with asset creation and categorization
- **Conversational AI Assistant**: Context-aware assistant with database knowledge
- **Action Suggestions**: AI-suggested actions for asset and maintenance management
- **LLM Integration**: Powered by Groq and OpenRouter APIs

### 📋 Audit & Compliance
- **Complete Audit Trails**: Every action logged with user and timestamp
- **Change History**: Track all modifications to critical data
- **Action Logging**: Create, Edit, Delete, Assign, Transfer, Return, Retire actions
- **Compliance Ready**: Generate audit reports for compliance verification
- **Data Snapshots**: Snapshot fields for historical accuracy (asset names, serial numbers)

### 🔐 Security & Access Control
- **JWT Authentication**: Stateless token-based authentication
- **Role-Based Access Control (RBAC)**: Fine-grained permission management
- **Four Built-in Roles**: System Admin, Operations Manager, External Technician, Employee
- **Custom Permissions**: Define granular permissions per role
- **Password Policies**: Must-change-password enforcement for new users
- **Token Invalidation**: Instant token invalidation for password resets

## Architecture

Quorum follows a modern layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────┐
│      Frontend (Angular/Ionic)       │
│      Web & Mobile Clients           │
└────────────────┬────────────────────┘
                 │ REST API (JWT Auth)
┌────────────────▼────────────────────┐
│  Django REST API Backend            │
│  ├─ Authentication & Authorization  │
│  ├─ Asset Management                │
│  ├─ Maintenance Workflow            │
│  ├─ Notifications & Real-time       │
│  ├─ AI/LLM Integration              │
│  └─ Audit & Compliance              │
└────────────────┬────────────────────┘
                 │
        ┌────────┼────────┐
        │        │        │
   ┌────▼───┐ ┌──▼──┐ ┌──▼──┐
   │PostgreSQL Redis Firebase
   │        │        │
   └────────┴────────┴──────┘
```

## Tech Stack

### Backend
- **Framework**: Django 6.0.4 with Django REST Framework 3.17.1
- **Language**: Python 3.10+
- **Database**: PostgreSQL (with SQLite support for development)
- **Authentication**: JWT (djangorestframework_simplejwt 5.5.1)
- **Real-time**: Django Channels 4.x with Redis
- **Web Server**: Gunicorn 26.2.0
- **Static Files**: WhiteNoise 6.12.0
- **Notifications**: Firebase Admin SDK 7.4.0 (optional)

### Frontend
- **Framework**: Angular 20.3.25
- **Mobile**: Ionic 8.0.0 + Capacitor 8.4.2 (iOS/Android)
- **Styling**: Tailwind CSS 3.4.17
- **State Management**: RxJS 7.8.0
- **Testing**: Karma/Jasmine

### Infrastructure
- **Container**: Docker compatible
- **Deployment**: Heroku, Railway, AWS, Kubernetes, Traditional Servers
- **Storage**: Media files support with WhiteNoise
- **Caching**: Redis for Channels and caching

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.10 or higher
- PostgreSQL 12 or higher (or use SQLite for development)
- pip (Python package manager)
- Virtual environment tool (venv or similar)
- Git
- (Optional) Docker for containerization

### Installation

1. **Clone the repository**:
```bash
git clone https://github.com/yourusername/quorum.git
cd quorum/quorum-backend
```

2. **Create and activate a virtual environment**:
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

### Configuration

1. **Copy the environment template**:
```bash
cp .env.example .env
```

2. **Configure your `.env` file** with appropriate values:

```bash
# Django Configuration
DEBUG=True
SECRET_KEY=your-secret-key-here-change-in-production

# Database Configuration
# For PostgreSQL:
DATABASE_URL=postgresql://user:password@localhost:5432/quorum_db

# For SQLite (development):
DATABASE_URL=sqlite:///db.sqlite3

# LLM/AI Services
GROQ_API_KEY=your-groq-api-key
OPENROUTER_API_KEY=your-openrouter-api-key

# Firebase (optional, for push notifications)
FIREBASE_CREDENTIALS_PATH=/path/to/service-account.json
```

3. **Run migrations**:
```bash
python manage.py migrate
```

4. **Create a superuser account**:
```bash
python manage.py createsuperuser
```

### Running the Backend

**Development Server**:
```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000`

**For production deployment**, see the [Deployment](#deployment) section.

## Project Structure

```
quorum-backend/
├── apps/                          # Django applications
│   ├── ai/                       # AI/LLM integration
│   ├── assets/                   # Asset management
│   ├── audit/                    # Audit logging
│   ├── authentication/           # Auth endpoints
│   ├── dashboard/                # Dashboard metrics
│   ├── users/                    # User management
│   ├── maintenance/              # Maintenance requests
│   ├── depreciation/             # Depreciation calculations
│   ├── notifications/            # Real-time notifications
│   ├── purchases/                # Purchase tracking
│   ├── reports/                  # Reporting features
│   ├── company_settings/         # Organization settings
│   └── common/                   # Shared utilities
├── config/                        # Django configuration
│   ├── settings.py               # Main settings
│   ├── urls.py                   # URL routing
│   ├── wsgi.py                   # WSGI entry point
│   └── asgi.py                   # ASGI entry point (Channels)
├── manage.py                      # Django management utility
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment template
├── Procfile                       # Deployment configuration
├── DEPLOYMENT_GUIDE.md            # Deployment instructions
├── SECURITY.md                    # Security documentation
└── README.md                      # This file
```

## API Documentation

### Authentication
All API endpoints require JWT authentication. Include the token in the Authorization header:

```bash
Authorization: Bearer <your-jwt-token>
```

### Base URL
```
http://localhost:8000/api/
```

### Main Endpoints

#### Authentication
- `POST /auth/login/` - User login
- `POST /auth/refresh/` - Refresh JWT token
- `POST /auth/logout/` - User logout

#### Assets
- `GET /assets/` - List all assets
- `POST /assets/` - Create new asset
- `GET /assets/{id}/` - Get asset details
- `PUT /assets/{id}/` - Update asset
- `DELETE /assets/{id}/` - Delete asset
- `GET /assets/{id}/units/` - Get asset units

#### Asset Assignments
- `GET /assignments/` - List assignments
- `POST /assignments/` - Create assignment
- `PUT /assignments/{id}/` - Update assignment
- `POST /assignments/{id}/return/` - Return asset

#### Maintenance
- `GET /maintenance/` - List maintenance requests
- `POST /maintenance/` - Create request
- `PUT /maintenance/{id}/` - Update request
- `PUT /maintenance/{id}/status/` - Update status

#### Users
- `GET /users/` - List users (admin only)
- `POST /users/` - Create user (admin only)
- `GET /users/profile/` - Get current user profile
- `PUT /users/{id}/` - Update user

#### Notifications
- `GET /notifications/` - Get user notifications
- `GET /notifications/unread-count/` - Get unread count
- `PUT /notifications/{id}/` - Mark as read

#### Dashboard
- `GET /dashboard/` - Get dashboard metrics
- `GET /dashboard/summary/` - Get quick summary

#### Depreciation
- `GET /depreciation/` - Get depreciation data
- `GET /depreciation/calculate/` - Calculate depreciation

For complete API documentation, please refer to the API specification or Swagger documentation (if enabled).

## Core Modules

### 1. Asset Management (`apps/assets`)
Handles complete asset lifecycle including creation, tracking, assignment, and retirement.

**Key Models:**
- `Asset` - Main asset records with financial data
- `AssetCategory` - Asset categorization
- `AssetUnit` - Individual units with serial numbers
- `AssetAssignmentHistory` - Complete assignment audit trail
- `AssetRequest` - Employee asset requests

### 2. User Management (`apps/users`, `apps/authentication`)
Manages user accounts, roles, permissions, and authentication.

**Key Features:**
- Custom user model with role-based system
- Four built-in roles with customizable permissions
- Department and employee ID tracking
- Mandatory password change on first login

### 3. Maintenance Management (`apps/maintenance`)
Tracks maintenance requests from creation to completion.

**Key Models:**
- `MaintenanceRequest` - Maintenance ticket tracking
- `MaintenanceTimelineEntry` - Historical status changes

**Statuses:** Pending → ToDo → In Progress → Review → Completed → Verified

### 4. Notifications (`apps/notifications`)
Real-time notification system with Firebase integration.

**Key Features:**
- In-app and push notifications
- User preference management
- FCM device token tracking
- Multiple notification types

### 5. Audit & Compliance (`apps/audit`)
Complete audit trail for compliance and financial reporting.

**Tracked Actions:**
- Create, Edit, Delete operations
- Asset assignments and transfers
- Return and retirement events

### 6. Depreciation (`apps/depreciation`)
Automatic asset depreciation calculation and tracking.

**Features:**
- Straight-line depreciation
- Salvage value tracking
- Useful life configuration

### 7. AI Assistance (`apps/ai`)
AI-powered features using Groq and OpenRouter APIs.

**Capabilities:**
- Issue description generation
- Asset categorization assistance
- Conversational AI assistant

## Authentication & Authorization

### Roles & Permissions

**System Admin**
- Full system access
- User management
- Configuration management
- All asset and maintenance operations

**Operations Manager**
- Asset management and assignment
- Maintenance workflow management
- Report generation
- User management (limited)

**External Technician**
- Maintenance request management
- Technician assignment handling
- Status updates
- Limited view access

**Employee**
- View assigned assets
- Request maintenance
- View notifications
- View own profile

### Permission Model
```python
Permission format: '<resource>.<action>'
Examples: 'asset.view', 'asset.create', 'asset.edit', 'maintenance.manage'
```

## Environment Variables

### Required Variables

```bash
# Django Core
DEBUG=False
SECRET_KEY=<generate-unique-secret-key>

# Database
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<dbname>?sslmode=require

# LLM Services
GROQ_API_KEY=<your-groq-api-key>
OPENROUTER_API_KEY=<your-openrouter-api-key>

# Firebase (Optional)
FIREBASE_CREDENTIALS_PATH=/path/to/service-account.json
```

### Development-Only Variables

```bash
# Local development
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
SECRET_KEY=dev-secret-key-only-for-testing
```

For more details, see [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md).

## Deployment

### Supported Platforms

- **Traditional Servers**: VPS, Dedicated Hosting
- **PaaS**: Heroku, Railway, Render
- **Containers**: Docker, Kubernetes
- **Serverless**: AWS Lambda, Google Cloud Functions (with setup)
- **Cloud Platforms**: AWS, Google Cloud, Azure

### Quick Deployment

1. **Docker**:
```bash
docker build -t quorum-backend .
docker run -p 8000:8000 --env-file .env quorum-backend
```

2. **Heroku**:
```bash
heroku create your-app-name
git push heroku main
heroku run python manage.py migrate
heroku run python manage.py createsuperuser
```

3. **Railway**:
```bash
railway up
```

For comprehensive deployment instructions, see [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md).

## Security

### Security Features

✅ **JWT Authentication**: Stateless, token-based authentication
✅ **RBAC**: Role-based access control with granular permissions
✅ **Environment Variables**: No hardcoded secrets
✅ **CORS Protection**: Configurable allowed origins
✅ **CSRF Protection**: Django's built-in CSRF middleware
✅ **Password Hashing**: Django's secure password validators
✅ **HTTPS Enforcement**: TLS/SSL in production
✅ **Audit Logging**: Complete audit trail for compliance

### Before Deploying to Production

- [ ] Generate new `SECRET_KEY`
- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS` with your domain
- [ ] Set up PostgreSQL with SSL
- [ ] Configure CORS `ALLOWED_ORIGINS` (restrict from `*`)
- [ ] Enable HTTPS/SSL certificates
- [ ] Run security checks: `python manage.py check --deploy`
- [ ] Set up monitoring and logging
- [ ] Review SECURITY.md documentation

For detailed security information, see [SECURITY.md](./SECURITY.md).

## Testing

### Run Backend Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.assets

# Run specific test class
python manage.py test apps.assets.tests.AssetTestCase

# Run with coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
```

### Test Structure
Each app includes a `tests.py` file with unit and integration tests.

### Frontend Testing (Angular)

```bash
# Navigate to frontend directory
cd ../quorum-frontend

# Run tests
npm test

# Run with coverage
npm test -- --code-coverage
```

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository** and create a feature branch
2. **Follow code style**: PEP 8 for Python, Angular style guide for TypeScript
3. **Write tests** for new features
4. **Document changes** in commit messages
5. **Submit a Pull Request** with a clear description

## Troubleshooting

### Common Issues

**Issue**: Database connection error
- **Solution**: Verify `DATABASE_URL` is correct and database server is running

**Issue**: `SECRET_KEY` not set
- **Solution**: Generate and set `SECRET_KEY` in .env file: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`

**Issue**: Permission denied on migrations
- **Solution**: Ensure database user has necessary privileges

**Issue**: Firebase notifications not working
- **Solution**: Verify `FIREBASE_CREDENTIALS_PATH` is set and file exists (optional feature)

**Issue**: CORS errors in frontend
- **Solution**: Add frontend URL to `CORS_ALLOWED_ORIGINS` in settings.py

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or contributions:
- 📧 Email: fareumair7@gmail.com
- 🐛 GitHub: [github.com/umairlabs](https://github.com/umairlabs)

---

**Quorum Asset Management System** - Simplifying enterprise asset management with intelligent tracking, maintenance workflows, and complete audit compliance.
