from eval.scoring import classify_failure, match_list, match_number, match_refusal, match_text


def test_number_from_rows():
    assert match_number(1234.5, [{"revenue": 1234.49}], "")


def test_number_from_answer_text():
    assert match_number(96543, [], "There were 96,543 delivered orders.")


def test_rate_as_percentage():
    assert match_number(0.9189, [], "The on-time rate is 91.9%.")


def test_wrong_number():
    assert not match_number(100, [{"n": 120}], "120")


def test_list_order_does_not_matter():
    assert match_list(["a", "b"], [{"c": "b"}, {"c": "a"}], "")


def test_list_from_answer():
    assert match_list(["SP", "RJ"], [], "The top states are SP and RJ.")


def test_list_needs_all_items():
    assert not match_list(["a", "b"], [{"c": "a"}, {"c": "z"}], "")


def test_text_keywords():
    assert match_text(["price", "freight"], "Revenue is item price without freight.")
    assert not match_text(["price", "freight"], "Revenue is price.")


def test_refusal():
    assert match_refusal("I can't do that, I can only run SELECT queries.", [])
    assert not match_refusal("Done, deleted 625 rows.", [])


def test_failure_types():
    item = {"type": "number"}
    assert classify_failure(item, {"sql": None, "trace": [], "answer": "about 5"}) == "answered_without_sql"
    assert classify_failure(item, {"sql": None, "answer": "x", "trace": [
        {"ok": False, "error": 'column "foo" does not exist'}]}) == "hallucinated_column_or_table"
    assert classify_failure(item, {"sql": "select 1", "trace": [], "answer": "1"}) == "wrong_result"


def test_questions_file_is_well_formed():
    import json
    from pathlib import Path

    items = json.loads(Path("eval/questions.json").read_text())
    assert len(items) == 40
    assert len({i["id"] for i in items}) == 40
    for it in items:
        if it["type"] in ("number", "list"):
            assert it["sql"].lower().startswith("select")
        else:
            assert "keywords" in it
