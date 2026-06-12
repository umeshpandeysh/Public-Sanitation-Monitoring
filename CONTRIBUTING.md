# Contributing to Public Sanitation Monitoring

Thank you for your interest in contributing to this project! This guide will help you get started.

## Code of Conduct

By participating in this project, you agree to maintain a respectful, inclusive environment. We expect all contributors to:
- Use welcoming and inclusive language
- Respect differing viewpoints and experiences
- Accept constructive criticism gracefully
- Focus on what is best for the project

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/<your-username>/Public-Sanitation-Monitoring.git
cd Public-Sanitation-Monitoring
```

### 2. Set Up Development Environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Run Tests

```bash
pytest tests/ -v
```

### 4. Run Linter

```bash
flake8 . --max-line-length=120 --exclude=venv,notebooks
```

## Pull Request Process

1. **Branch Naming**: Use descriptive branch names:
   - `feature/add-co2-sensor-support`
   - `fix/anomaly-threshold-edge-case`
   - `docs/update-sensor-setup-guide`

2. **Commit Messages**: Follow the [Conventional Commits](https://www.conventionalcommits.org/) spec:
   ```
   feat: add IsolationForest anomaly detection method
   fix: correct Z-score calculation for small window sizes
   docs: improve sensor wiring diagram
   test: add edge cases for AnomalyDetector
   ```

3. **Before Submitting**:
   - [ ] All tests pass (`pytest tests/ -v`)
   - [ ] No flake8 linting errors
   - [ ] New features have test coverage ≥ 80%
   - [ ] Updated docstrings and `README.md` if API changed

4. **Pull Request Template**: Describe what, why, and how. Link related issues.

## Coding Standards

### Python Style

- Follow **PEP 8** with max line length of **120 characters**
- Use **type hints** for all function signatures
- Write **docstrings** (Google style) for all public classes and functions
- Use `logging` instead of `print` statements in library code

### Example

```python
def detect_threshold_anomaly(self, reading: Dict[str, float]) -> Dict:
    """Check reading values against configured thresholds.

    Args:
        reading: Sensor reading dictionary with parameter values.

    Returns:
        Dict with keys: status ('normal'|'warning'|'critical'),
        violations (list of dicts with parameter, value, threshold).
    """
    violations = []
    status = "normal"
    # ... implementation
    return {"status": status, "violations": violations}
```

### Testing Requirements

- Use `pytest` for all tests
- Name test files `test_<module>.py`
- Name test functions `test_<behaviour>_<expected_outcome>`
- Mock external dependencies (MQTT, filesystem) in unit tests
- Target ≥ 80% coverage for all new modules

## Reporting Issues

When filing a bug report, include:
- Python version and OS
- Steps to reproduce
- Expected vs. actual behaviour
- Relevant log output

## Feature Requests

Open a GitHub issue with the label `enhancement` and describe:
- The problem you are solving
- Your proposed solution
- Any alternative approaches considered

## Project Structure Overview

```
Public-Sanitation-Monitoring/
├── sensor/          # Sensor simulation & MQTT publishing
├── processing/      # Data cleaning, anomaly detection, alerts
├── dashboard/       # Streamlit real-time dashboard
├── api/             # Flask REST API
├── data/            # Sample datasets
├── config/          # YAML configuration files
├── docs/            # Hardware setup guides
├── notebooks/       # Analysis notebooks
└── tests/           # Unit test suite
```

Thank you for helping build smarter public infrastructure! 🏙️
