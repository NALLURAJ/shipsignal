.PHONY: setup db warehouse notebooks dashboard api app eval test lint sample tableau

setup:
	python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
	cp -n .env.example .env || true

db:
	docker compose up -d db

warehouse:
	python -m ingest.load_raw --data-dir data/raw
	cd warehouse/dbt_shipsignal && dbt build --profiles-dir .

notebooks:
	cd analysis && for nb in 0*.ipynb; do jupyter nbconvert --to notebook --execute --inplace $$nb; done

dashboard:
	python -m analysis.make_dashboard

api:
	uvicorn api.main:app --reload

app:
	streamlit run app/streamlit_app.py

eval:
	python -m eval.run_eval

tableau:
	python -m bi.export_for_tableau

test:
	pytest -q

lint:
	ruff check .
	cd warehouse/dbt_shipsignal && sqlfluff lint models tests

# synthetic data, same shape as olist, for trying the pipeline without the download
sample:
	python scripts/make_sample_data.py --out data/sample
	python -m ingest.load_raw --data-dir data/sample
	cd warehouse/dbt_shipsignal && dbt build --profiles-dir .
