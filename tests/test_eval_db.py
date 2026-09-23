import json
from pathlib import Path

import pytest

from assistant.guard import check_sql
from eval.run_eval import expected_answers

pytestmark = pytest.mark.db


def test_every_gold_query_runs_and_passes_the_guard():
    items = json.loads(Path("eval/questions.json").read_text())
    gold = expected_answers(items)
    for it in items:
        if it["type"] in ("number", "list"):
            check_sql(it["sql"])  # the assistant must be able to write the same query
            assert gold[it["id"]] not in (None, [], float("nan"))
