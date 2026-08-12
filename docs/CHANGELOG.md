# Changelog - Korgo Pro

Tous les changements notables de ce projet sont documentés ici.

Format basé sur [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
et ce projet suit le [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-08-12 (Unreleased)

### Added (Nouvelles Fonctionnalités)

#### UI/UX & Design
- 🎨 **Theme System**: Token-based design variables (`ui/themes/variables.json`)
  - Light/Dark theme palettes with 25+ customizable tokens
  - Runtime theme substitution in QSS files via theme manager
  - Enables rapid theme switching and consistent styling

- 🎯 **Responsive Menu Component**: Mobile-first navigation
  - Adapts between desktop sidebar (220px) and mobile drawer (250px)
  - Auto-detection: desktop (>768px) vs mobile (<768px)
  - Smooth animations and accessibility features

- 🧩 **Component Library** (`ui/components/`):
  - `CustomButton`: 4 variants (primary, secondary, danger, outline) + 4 sizes
  - `CustomCard`: Content containers with header, footer, elevation levels
  - `ResponsiveMenu`: Already described above
  - Full documentation + usage examples in [Component README](../ui/components/README.md)

- ♿ **Accessibility Improvements**:
  - Added `AccessibleName` and `AccessibleDescription` to login form elements
  - Extended accessibility labels to dashboard (user info, charts, tables)
  - Focus ring styling for keyboard navigation (2px solid accent)
  - Screen reader support for critical UI elements

#### Developer Experience
- 📚 **Comprehensive Documentation**:
  - [DEPLOYMENT.md](DEPLOYMENT.md): Production setup, backup strategy, troubleshooting
  - [CONTRIBUTING.md](CONTRIBUTING.md): Development workflow, code style, testing
  - [CHANGELOG.md](CHANGELOG.md): This file
  - Detailed guides on installation, debugging, maintenance

- 📋 **Database Configuration**:
  - Made `KORGO_DB_URL` environment variable configurable
  - Supports SQLite (dev) and PostgreSQL (production)
  - Graceful fallback to `sqlite:///korgo_pro.db`

- ⚙️ **Configuration Template**:
  - Added `.env.example` with all required variables
  - Documented SECRET_KEY generation and security practices
  - LOG_LEVEL, COMPANY_NAME, DEBUG_MODE options

- 🔄 **Data Organization**:
  - Moved reports, exports, and data files to `data/` folder
  - Added to `.gitignore` to prevent tracking large files
  - Data folder not pushed to repository (excludes PII from history)

- 🤖 **CI/CD Foundation**:
  - Added `.github/workflows/python-ci.yml` for automated testing
  - Installs dependencies and runs pytest on push/PR
  - Prepares foundation for code quality gates

### Changed (Améliorations)

- 🎨 **QSS Theme Updates** (`ui/themes/main.qss`):
  - Replaced hardcoded colors with token variables
  - Updated focus/hover states using {{PRIMARY}} and related tokens
  - Improved visual hierarchy with consistent spacing

- 🧠 **Theme Manager** (`ui/themes/theme_manager.py`):
  - Now loads `variables.json` and substitutes {{TOKEN}} placeholders
  - Enables dynamic theme switching without code changes
  - Reduces stylesheet duplication

### Security

- No hardcoded secrets in codebase
- Database credentials managed via `.env`
- Template `.env.example` shows non-sensitive defaults

### Deprecated

- Hardcoded color values in QSS files (use tokens instead)

### Technical

- **Commit**: `9000153` - Responsive menu + component library
- **Commit**: `7dd079c` - Theme tokens + accessibility
- **Commit**: `75d573d` - README + .env.example + DB config
- **Commit**: `06587fe` - Move data files to data/ folder

---

## [0.1.0] - 2026-07-XX (Initial Release)

### Added

- ✅ Initial project structure (core, ui, utils, controllers)
- ✅ PySide6-based desktop GUI
- ✅ User authentication system
- ✅ Sales management module
- ✅ Stock/inventory management
- ✅ PDF report export (invoices, benefits)
- ✅ Admin panel for company settings
- ✅ SQLAlchemy ORM for database abstraction
- ✅ Basic security (SHA256 password hashing - to be upgraded)

### Known Issues

- ⚠️ Passwords hashed with SHA256 (should migrate to bcrypt)
- ⚠️ No rate limiting on login attempts
- ⚠️ UI tests not automated
- ⚠️ Limited error handling in long-running operations
- ⚠️ Logs use print() instead of logger module

---

## Upcoming (Roadmap)

### [0.3.0] - Q4 2026

- [ ] Additional components: Input, Select, Table, Modal
- [ ] Theme switcher UI for users
- [ ] Bcrypt migration for password hashing
- [ ] Enhanced error handling and logging
- [ ] Unit tests for auth module
- [ ] Performance optimizations (DB indexing, query caching)

### [0.4.0] - Q1 2027

- [ ] Multi-language support (i18n)
- [ ] Mobile-responsive version (Kivy/web)
- [ ] Real-time sync with cloud backup
- [ ] Advanced reporting (custom queries, charts)
- [ ] Audit logging for compliance

### Future Ideas

- [ ] API for mobile/web access
- [ ] Machine learning for sales forecasting
- [ ] Automated invoice reminders
- [ ] Multi-user collaboration features
- [ ] Integration with accounting software (QuickBooks, etc.)

---

## Version History Summary

| Version | Date | Type | Notes |
|---------|------|------|-------|
| **0.2.0** | 2026-08-12 | ✨ Major | Design system, components, docs |
| **0.1.0** | 2026-07-XX | 🚀 Initial | MVP - core ERP features |

---

## How to Report Issues

When reporting bugs, please include:

1. **Version**: `git describe --tags` or version shown in About dialog
2. **OS**: Windows, Linux, macOS + version
3. **Steps to reproduce**: Exact sequence to trigger the bug
4. **Expected behavior**: What should happen
5. **Actual behavior**: What happens instead
6. **Screenshots/logs**: Error messages from console
7. **Environment**: Python version, database type, relevant config

Example:
```
Title: Login fails with PostgreSQL on Windows

Version: 0.2.0
OS: Windows 11 22H2
Python: 3.11.5

Steps:
1. Set KORGO_DB_URL=postgresql://user:pass@localhost:5432/korgo_pro
2. Launch app with `python main.py`
3. Enter admin/password

Expected: Login succeeds, dashboard loads
Actual: Error "could not translate host name... to address"

Error log:
[ERROR] sqlalchemy.exc.OperationalError: (psycopg2.OperationalError)
    could not translate host name "localhost" to address: Name or service not known

Environment:
- PostgreSQL 14 running on localhost:5432
- psycopg2-binary 2.9.6
```

---

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this project.

---

## License

[Specify your license: MIT, GPL, etc.]

---

**Last Updated**: 2026-08-12  
**Maintainer**: Korgo Team
