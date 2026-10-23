# Contributing to Passli

Thank you for your interest in contributing to **Passli**! We welcome contributions from developers, security researchers, and designers.

To ensure high engineering standards, security robustness, and clean git history, please review our contribution guidelines below.

---

## 🛠️ Code of Conduct & Maintainers

All contributors and maintainers are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). 

Project Maintainers:
- **Ali Nawaz** ([@alinawazcode](https://github.com/alinawazcode))
- **Muqadas Fareed** ([@Muqadas-Fareed-devt](https://github.com/Muqadas-Fareed-devt))

Please report any unacceptable behavior or queries to `alinawaz.code@gmail.com`.

---

## 🚀 Development Workflow

### 1. Fork & Clone
```bash
git clone https://github.com/<your-username>/passli.git
cd passli
```

### 2. Environment Setup
```bash
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py ensure_superadmin
```

### 3. Create a Feature Branch
```bash
git checkout -b feat/your-feature-name
```

---

## 📐 Engineering Standards & Guidelines

1. **Python & Django Standards**:
   - Adhere strictly to PEP 8 and idiomatic Django conventions.
   - Keep business logic in models or service layers, avoiding overly fat views.
   - Avoid N+1 queries by using `select_related()` and `prefetch_related()`.

2. **Security & Data Protection**:
   - Never hardcode secrets, passwords, or encryption keys in source code.
   - All sensitive variables must be retrieved from environment variables (`.env`).
   - Validate and sanitize all user input; protect against IDOR by checking ownership in all views.
   - Plaintext cryptographic keys must **never** be persisted to the database.

3. **UI / UX Design Aesthetics**:
   - Follow the Passli modern minimalist design system and styling standards.
   - Use clean, semantic HTML5 and Vanilla CSS tokens from `static/css/styles.css`.
   - Maintain full mobile responsiveness and avoid bloated CSS frameworks.

4. **Testing & Code Quality Discipline**:
   - Write comprehensive unit tests for all new models, views, forms, and utilities.
   - Run Ruff linter to verify code formatting and standards:
     ```bash
     ruff check accounts audit config documents sharing tests
     ```
   - Verify that all test suites pass with zero errors and meet the 80% coverage threshold:
     ```bash
     coverage run --source=accounts,audit,config,documents,sharing manage.py test tests.unit tests.selenium
     coverage report --fail-under=80
     ```

---

## 📝 Commit Convention

Passli follows the [Conventional Commits](https://www.conventionalcommits.org/) standard:

- `feat(...)`: Introduces a new user-facing feature or enhancement.
- `fix(...)`: Fixes a bug or unexpected behavior.
- `style(...)`: Formatting, CSS improvements, or UI refinements.
- `refactor(...)`: Code changes that neither fix a bug nor add a feature.
- `test(...)`: Adding or updating test suites.
- `docs(...)`: Documentation updates.
- `chore(...)`: Dependency updates, build configurations, or tooling.

*Example:*
```bash
git commit -m "feat(sharing): add duration selector for 48h ephemeral pass expiration"
```

---

## 📬 Submitting a Pull Request

1. Push your branch to your fork:
   ```bash
   git push origin feat/your-feature-name
   ```
2. Open a Pull Request against the `main` branch of the upstream repository.
3. Provide a clear description of the problem solved and include testing steps.
4. Ensure all CI automated checks and CodeRabbit reviews pass.
