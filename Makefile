.PHONY: install lint test manifest verify serve

install:
	python -m pip install -e '.[dev,ops]'

lint:
	ruff check artifactguard tests

test:
	python -m pytest tests -q

manifest:
	python artifactguard.py manifest examples artifacts/examples.manifest.json

verify:
	python artifactguard.py verify examples artifacts/examples.manifest.json

serve:
	uvicorn artifactguard.api:app --reload --port 8000
