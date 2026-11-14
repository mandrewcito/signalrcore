.PHONY: dev-install tests unit-tests integration-tests package lint all upload github-pages clean

dev-install:
	python3 -m venv venv
	venv/bin/pip install .[dev]

# Full suite: unit tests plus integration tests.
# Integration tests need the signalrcore containers running.
tests:
	@mkdir -p reports
	venv/bin/pytest --junitxml=reports/junit.xml --cov=. --cov-report=html:coverage_html --cov-report=xml:coverage.xml --cov-report=term

# Offline only: no SignalR server or Azure function required.
unit-tests:
	@mkdir -p reports
	venv/bin/pytest test/unit --junitxml=reports/junit-unit.xml

# Integration only: requires the signalrcore containers running.
integration-tests:
	@mkdir -p reports
	venv/bin/pytest test/integration --junitxml=reports/junit-integration.xml

package:
	python3 -m build

lint:
	venv/bin/flake8 signalrcore test

all:
	tests package

upload:
	venv/bin/twine upload dist/* --verbose

github-pages:
	docker run --rm \
	--volume="$(pwd)/docs:/srv/jekyll" \
	-p 4000:4000 \
	jekyll/jekyll:4 \
	jekyll serve --watch --force_polling

clean:
	@find . -name "*.pyc" -exec rm -f '{}' +
	@find . -name "*~" -exec rm -f '{}' +
	@find . -name "__pycache__" -exec rm -R -f '{}' +
	@rm -rf build/
	@rm -rf coverage_html/
	@rm -rf dist/
	@rm -rf signalrcore.egg-info/
	@rm -rf .pytest_cache/
	@rm -rf reports/
	@rm -rf .coverage
	@rm -rf coverage.xml
	@echo "Done!"
