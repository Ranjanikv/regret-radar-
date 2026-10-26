.PHONY: setup data load score app test demo

PYTHON ?= python

setup:
	$(PYTHON) -m pip install -r requirements.txt

data:
	$(PYTHON) -m data_gen.generate --scale small

load:
	$(PYTHON) -m load.bulk_load

score:
	$(PYTHON) -m load.run_scoring

app:
	streamlit run app/main.py

test:
	ruff check .
	pytest

demo:
	$(PYTHON) -m load.demo
