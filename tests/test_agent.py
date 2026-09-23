import pytest

from assistant.agent import MAX_STEPS, Assistant, parse_reply
from assistant.llm import Reply
from assistant.retrieval import Chunk, DefinitionIndex, split_markdown


class ScriptedLLM:
    """Returns canned replies in order, and remembers what it was sent."""

    model = "scripted"

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def chat(self, messages):
        self.seen.append(list(messages))
        return Reply(self.replies.pop(0), prompt_tokens=100, output_tokens=10, seconds=0.01, cached=False)


def fake_sql(sql):
    if "boom" in sql:
        return {"ok": False, "error": 'column "boom" does not exist', "kind": "database"}
    return {"ok": True, "sql": sql, "columns": ["n"], "rows": [{"n": 42}]}


@pytest.fixture
def index():
    return DefinitionIndex([
        Chunk("Revenue", "Revenue is the sum of item prices. It does not include freight."),
        Chunk("On-time delivery", "On time means delivered on or before the estimated delivery date."),
    ])


def test_parse_reply_plain_json():
    assert parse_reply('{"answer": "hi"}') == {"answer": "hi"}


def test_parse_reply_wrapped_json():
    assert parse_reply('Sure! {"tool": "run_sql", "sql": "select 1"} hope that helps')["tool"] == "run_sql"


def test_parse_reply_not_json_becomes_answer():
    assert parse_reply("no idea") == {"answer": "no idea"}


def test_sql_then_answer(index):
    llm = ScriptedLLM(['{"tool": "run_sql", "sql": "select 42 as n"}', '{"answer": "There are 42."}'])
    out = Assistant(llm, "v3", index=index, run_sql=fake_sql).ask("how many?")
    assert out["answer"] == "There are 42."
    assert out["rows"] == [{"n": 42}]
    assert out["tools_used"] == ["run_sql"]
    assert out["usage"]["llm_calls"] == 2
    # the tool result is sent back to the model
    assert "TOOL RESULT" in llm.seen[1][-1]["content"]


def test_sql_error_is_returned_to_model(index):
    llm = ScriptedLLM(['{"tool": "run_sql", "sql": "select boom"}',
                       '{"tool": "run_sql", "sql": "select 42 as n"}',
                       '{"answer": "42"}'])
    out = Assistant(llm, "v2", index=index, run_sql=fake_sql).ask("q")
    assert out["trace"][0]["ok"] is False
    assert "does not exist" in llm.seen[1][-1]["content"]
    assert out["answer"] == "42"


def test_step_limit(index):
    llm = ScriptedLLM(['{"tool": "run_sql", "sql": "select 1"}'] * MAX_STEPS)
    out = Assistant(llm, "v3", index=index, run_sql=fake_sql).ask("loop forever")
    assert "step limit" in out["answer"]


def test_unknown_tool(index):
    llm = ScriptedLLM(['{"tool": "rm_rf"}', '{"answer": "ok"}'])
    out = Assistant(llm, "v3", index=index, run_sql=fake_sql).ask("q")
    assert out["trace"][0]["ok"] is False


def test_retrieval_adds_context(index):
    llm = ScriptedLLM(['{"answer": "Revenue excludes freight."}'])
    Assistant(llm, "v3", index=index, run_sql=fake_sql).ask("how is revenue defined?")
    assert "does not include freight" in llm.seen[0][1]["content"]


def test_no_retrieval_means_no_context():
    llm = ScriptedLLM(['{"tool": "lookup_definition", "term": "revenue"}', '{"answer": "?"}'])
    bot = Assistant(llm, "v1", use_retrieval=False, run_sql=fake_sql)
    out = bot.ask("how is revenue defined?")
    assert "Relevant definitions" not in llm.seen[0][1]["content"]
    assert out["trace"][0]["ok"] is False


def test_chart_uses_last_rows(index):
    llm = ScriptedLLM(['{"tool": "run_sql", "sql": "select 1"}',
                       '{"tool": "make_chart", "x": "n", "y": "n", "kind": "line"}',
                       '{"answer": "done"}'])
    out = Assistant(llm, "v3", index=index, run_sql=fake_sql).ask("chart it")
    assert out["chart"]["kind"] == "line"


def test_split_markdown():
    chunks = split_markdown("# Title\n\n## A\ntext a\n\n## B\ntext b\n")
    assert [c.title for c in chunks] == ["A", "B"]


def test_real_definitions_file_is_searchable():
    idx = DefinitionIndex.from_files()
    titles = [c.title.lower() for c in idx.search("what does on time delivery mean", k=2)]
    assert "on-time delivery" in titles
