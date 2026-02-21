dev-install:
	python3 -m venv venv
	venv/bin/pip install .[dev]

tests:
	venv/bin/python3 -m unittest discover -s test/ -p "*_test.py" -v

package:
	python3 -m build

lint:
	venv/bin/flake8 signalrcore test

all:
	tests package

upload:
	venv/bin/twine upload dist/* --verbose

coverage:
	venv/bin/coverage run -m unittest discover -s test/ -p "*_test.py"
	venv/bin/coverage html --omit="venv/*" -d coverage_html

pytest-cov:
	venv/bin/pytest --junitxml=reports/junit.xml --cov=. --cov-report=html:coverage_html --cov-report=xml:coverage.xml --cov-report=term
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
