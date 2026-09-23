"""The question-answering loop.

The model picks one tool per turn (JSON reply), we run it, send the result
back, and repeat until it answers or runs out of steps.
"""

import json
import logging
import os
from typing import Any

from assistant import tools
from assistant.llm import OllamaClient
from assistant.prompts import system_prompt
from assistant.retrieval import DefinitionIndex

log = logging.getLogger("assistant")

MAX_STEPS = 5
ROWS_SHOWN_TO_MODEL = 20


def parse_reply(text: str) -> dict[str, Any]:
    """Pull the JSON object out of the model reply. Small models sometimes wrap it."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    return {"answer": text}


class Assistant:
    def __init__(self, llm: OllamaClient, prompt_version: str = "v3", use_retrieval: bool = True,
                 index: DefinitionIndex | None = None, run_sql=tools.run_sql):
        self.llm = llm
        self.prompt_version = prompt_version
        self.use_retrieval = use_retrieval
        self.index = index or (DefinitionIndex.from_files() if use_retrieval else None)
        self.run_sql = run_sql

    @classmethod
    def from_env(cls) -> "Assistant":
        return cls(
            OllamaClient.from_env(),
            prompt_version=os.environ.get("ASSISTANT_PROMPT", "v3"),
            use_retrieval=os.environ.get("ASSISTANT_RAG", "1") == "1",
        )

    def _context(self, question: str) -> str:
        if not self.index:
            return ""
        hits = self.index.search(question, k=2)
        if not hits:
            return ""
        notes = "\n\n".join(f"[{h.title}]\n{h.text}" for h in hits)
        return f"\n\nRelevant definitions from the project docs:\n{notes}"

    def ask(self, question: str) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt(self.prompt_version)},
            {"role": "user", "content": question + self._context(question)},
        ]
        out: dict[str, Any] = {"answer": "", "sql": None, "rows": [], "chart": None,
                               "tools_used": [], "trace": [],
                               "usage": {"prompt_tokens": 0, "output_tokens": 0, "llm_seconds": 0.0, "llm_calls": 0}}

        for _ in range(MAX_STEPS):
            reply = self.llm.chat(messages)
            u = out["usage"]
            u["prompt_tokens"] += reply.prompt_tokens
            u["output_tokens"] += reply.output_tokens
            u["llm_seconds"] += reply.seconds
            u["llm_calls"] += 1

            action = parse_reply(reply.content)
            messages.append({"role": "assistant", "content": reply.content})

            if "answer" in action and "tool" not in action:
                out["answer"] = str(action["answer"])
                return out

            tool = action.get("tool")
            out["tools_used"].append(tool)
            result = self._run_tool(tool, action, out)
            out["trace"].append({"tool": tool, "input": action, "ok": result.get("ok"),
                                 "error": result.get("error")})

            shown = dict(result)
            if "rows" in shown:
                shown["rows"] = shown["rows"][:ROWS_SHOWN_TO_MODEL]
                shown["row_count"] = len(result["rows"])
            messages.append({"role": "user", "content": "TOOL RESULT: " + json.dumps(shown, default=str)})

        out["answer"] = "I couldn't finish answering that within the step limit."
        return out

    def _run_tool(self, tool: str | None, action: dict, out: dict) -> dict:
        if tool == "run_sql":
            result = self.run_sql(action.get("sql", ""))
            if result.get("ok"):
                out["sql"] = result["sql"]
                out["rows"] = result["rows"][:50]
            return result
        if tool == "lookup_definition":
            if not self.index:
                return {"ok": False, "error": "definitions are not available in this configuration"}
            return tools.lookup_definition(self.index, str(action.get("term", "")))
        if tool == "make_chart":
            result = tools.make_chart(out["rows"], str(action.get("x")), str(action.get("y")),
                                      str(action.get("kind", "bar")))
            if result.get("ok"):
                out["chart"] = result["chart"]
            return result
        return {"ok": False, "error": f"unknown tool {tool!r}; use run_sql, lookup_definition, make_chart or answer"}
