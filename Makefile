# Public-Sanitation-Monitoring — Project Makefile
.PHONY: help install test lint simulate dashboard api clean

PYTHON ?= python

help:       ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?##"}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:    ## Install all dependencies
	pip install -r requirements.txt

test:       ## Run the full test suite
	pytest tests/ -v --tb=short

lint:       ## Lint with flake8
	flake8 sensor/ processing/ api/ tests/ --max-line-length=100 --ignore=E203,W503

simulate:   ## Run sensor simulator (5 seconds)
	$(PYTHON) -c "from sensor.simulator import SensorSimulator; s=SensorSimulator(['A1','A2']); [print(r) for r in s.generate_batch(10)]"

dashboard:  ## Launch the Streamlit dashboard
	streamlit run dashboard/streamlit_app.py

api:        ## Start the Flask REST API
	$(PYTHON) api/server.py

clean:      ## Remove generated files
	rm -rf logs/ data/alerts.csv
	@echo "Cleaned."
