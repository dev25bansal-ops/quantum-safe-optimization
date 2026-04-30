# Contributing to Quantum-Safe Optimization Platform

Thank you for your interest in contributing to QSOP!

## Development Setup

### Prerequisites

- Python 3.11+
- Rust 1.75+ (for crypto module)
- Docker & Docker Compose
- Git

### Getting Started

```bash
# Clone the repository
git clone https://github.com/your-org/quantum-safe-optimization.git
cd quantum-safe-optimization

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/ -v

# Run linters
ruff check src/
mypy src/
```

## Code Style

### Python

- Follow PEP 8 with line length of 100 characters
- Use type hints for all public functions
- Use docstrings for classes and public methods
- Use `ruff` for formatting and linting

### Rust

- Follow standard Rust formatting (`cargo fmt`)
- Run `cargo clippy` before committing

## Commit Guidelines

### Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance

### Examples

```
feat(crypto): add ML-KEM-1024 support

fix(auth): prevent token reuse after logout

docs(api): add endpoint documentation for job cancellation
```

## Pull Request Process

1. **Create a branch** from `main`:

   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make your changes** with clear commits

3. **Add tests** for new functionality

4. **Run the test suite**:

   ```bash
   pytest tests/ -v --cov
   ```

5. **Run linters**:

   ```bash
   ruff check src/
   mypy src/
   ```

6. **Push and create PR**:

   ```bash
   git push origin feat/my-feature
   ```

7. **Address review feedback**

### PR Checklist

- [ ] Tests pass
- [ ] New code has test coverage
- [ ] Documentation updated
- [ ] Changelog updated (if applicable)
- [ ] No secrets in code
- [ ] Type hints added
- [ ] Breaking changes documented

## Security

### Reporting Vulnerabilities

**DO NOT** open a public issue for security vulnerabilities.

Email: security@your-domain.com

Include:

- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Security Guidelines

- Never commit secrets, API keys, or passwords
- Use environment variables for configuration
- Validate all user inputs
- Use parameterized queries for database operations
- Sign all job results with ML-DSA
- Encrypt sensitive data at rest

## Testing

### Unit Tests

```bash
pytest tests/unit/ -v
```

### Integration Tests

```bash
pytest tests/integration/ -v
```

### Coverage

```bash
pytest --cov=src/qsop --cov-report=html
```

Target: 80% coverage minimum

## Documentation

### API Documentation

- Use OpenAPI annotations in FastAPI
- Document all request/response models
- Include examples in Pydantic models

### Code Documentation

- Use docstrings for public functions
- Include type hints
- Document security implications

## Project Structure

```
src/qsop/
├── api/           # REST API endpoints
├── application/   # Business logic
├── backends/      # Quantum backend integrations
├── crypto/        # PQC implementations
├── domain/        # Core domain models
├── infrastructure/# External integrations
├── optimizers/    # Optimization algorithms
└── security/      # Security utilities
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Architecture Decision Records

For significant architectural decisions, we use ADRs. See `docs/adr/` for existing decisions.

When making architectural changes:

1. Create an ADR in `docs/adr/NNNN-title.md`
2. Use the ADR template
3. Link the ADR in your PR

## GraphQL API

We support both REST and GraphQL APIs:

```bash
# Access GraphQL playground
http://localhost:8000/api/v1/graphql
```

When adding endpoints, consider both APIs.

## Chaos Engineering

We use chaos tests to verify system resilience:

```bash
pytest tests/chaos/ -v
```

## Questions?

- Open a GitHub Discussion for general questions
- Open a GitHub Issue for bugs/features
- Email: team@qsop.dev

## Recognition

Contributors are listed in CONTRIBUTORS.md. Thank you for making QSOP better!
