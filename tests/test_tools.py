"""Offline tests: the actions against a local stand-in for the API on 127.0.0.1, by a plain call, as browser-use's
Tools registers them, and by the Pydantic AI tools browser-use's Agent hands its model, on a scripted model."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
from browser_use import Tools
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

import browser_use_datacircle as dc
from browser_use_datacircle import DatacircleError, _api, add_datacircle_tools, datacircle_tools

OURS = ["datacircle_list_apis", "datacircle_best_plans", "datacircle_search_plans", "datacircle_provider"]
PLAN = {"api": "Employee email", "rank": 1, "provider": "Hunter", "plan": "Starter", "score": 80.1, "perThousand": 4.9,
        "page": "https://datacircle.dev/x", "terms": "long", "aggregators": ["a"]}
SEEN = []
BUSY = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urlparse(self.path)
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        SEEN.append((url.path, query, self.headers.get("User-Agent")))
        headers = {}
        if url.path == "/v1/plans" and query.get("query") == "busy" and not BUSY:
            BUSY.append(1)
            status, body, headers = 429, {"error": "slow down"}, {"Retry-After": "1"}
        elif url.path == "/v1/apis":
            status, body = 200, [{"api": "Employee email", "slug": "email-finder", "plans": 9, "providers": 3, "extra": 1},
                                 {"api": "Employee profile", "slug": "linkedin-profile", "plans": 4, "providers": 2}]
        elif url.path == "/v1/apis/email-finder/best":
            status, body = 200, {"api": "Employee email", "slug": "email-finder", "total": 1, "plans": [PLAN]}
        elif url.path.startswith("/v1/apis/"):
            status, body = 404, {"error": "no API has the slug nope", "slugs": ["email-finder", "linkedin-profile"]}
        elif url.path == "/v1/plans" and query.get("query") == "refused":
            status, body = 400, {"error": "query refused by the stand-in"}
        elif url.path == "/v1/plans":
            status, body = 200, {"total": 1, "offset": 0, "plans": [PLAN]}
        elif url.path == "/v1/providers/bright-data":
            status, body = 200, {"provider": "Bright Data", "slug": "bright-data", "website": "https://brightdata.com",
                                 "apis": [{"api": "Employee email", "slug": "email-finder", "rank": 7, "sheetPage": "s",
                                           "plans": [dict(PLAN, rank=9, plan="B"), dict(PLAN, rank=7, plan="A")]}]}
        else:
            status, body = 404, {"error": "no provider has this slug"}
        data = json.dumps(body).encode()
        self.send_response(status)
        for key, value in {"Content-Type": "application/json", "Content-Length": str(len(data)), **headers}.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module", autouse=True)
def stand_in():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    before = _api.BASE_URL
    _api.BASE_URL = f"http://127.0.0.1:{server.server_address[1]}/v1"
    yield
    _api.BASE_URL = before
    server.shutdown()


def test_what_the_model_reads():
    defs = {tool.name: tool.tool_def for tool in datacircle_tools().functions}
    assert list(defs) == OURS
    search = defs["datacircle_search_plans"].parameters_json_schema
    assert search["properties"]["sort"]["anyOf"][0]["enum"] == ["score", "provider", "price"]
    assert search["properties"]["limit"]["anyOf"][0] == {"maximum": 50, "minimum": 1, "type": "integer"}
    assert defs["datacircle_best_plans"].parameters_json_schema["required"] == ["slug"]
    for made in defs.values():
        assert "https://datacircle.dev" in made.description and "\n" not in made.description
        for name, field in made.parameters_json_schema["properties"].items():
            assert field["description"] and "\n" not in field["description"]


def test_added_beside_your_own_actions():
    tools = Tools()

    @tools.action("Counts the words of a text")
    def word_count(text: str) -> int:
        return len(text.split())

    assert add_datacircle_tools(tools) is tools
    add_datacircle_tools(tools)
    assert [tool.name for tool in tools.functions] == ["word_count", *OURS]
    assert dc.datacircle_best_plans.__name__ == "datacircle_best_plans"


def test_calls_sent_and_answers_cut():
    SEEN.clear()
    apis = dc.datacircle_list_apis(query="profile")
    assert apis == {"total": 1, "apis": [{"api": "Employee profile", "slug": "linkedin-profile", "plans": 4, "providers": 2}]}
    best = dc.datacircle_best_plans("Email Finder", limit="3")
    assert best["plans"] == [{key: PLAN[key] for key in ["api", "rank", "provider", "plan", "score", "perThousand", "page"]}]
    plans = dc.datacircle_search_plans(api="email-finder", query="hunter", sort="PRICE")
    assert plans["total"] == 1
    provider = dc.datacircle_provider("Bright Data")
    assert provider["apis"][0]["best"]["plan"] == "A" and provider["apis"][0]["plans"] == 2
    assert [path for path, _, _ in SEEN] == ["/v1/apis", "/v1/apis/email-finder/best", "/v1/plans", "/v1/providers/bright-data"]
    assert SEEN[1][1] == {"limit": "3"}
    assert SEEN[2][1] == {"api": "email-finder", "query": "hunter", "sort": "price"}
    assert all(agent.startswith("browser-use-datacircle/") for _, _, agent in SEEN)


def test_refusals_raise_with_their_words():
    SEEN.clear()
    with pytest.raises(DatacircleError, match="no API has the slug nope; the slugs: email-finder, linkedin-profile"):
        dc.datacircle_best_plans("nope")
    with pytest.raises(DatacircleError, match="^Datacircle's API answered 400: query refused by the stand-in$"):
        dc.datacircle_search_plans(query="refused")
    with pytest.raises(DatacircleError, match="no provider"):
        dc.datacircle_provider("nobody")
    refused = [lambda: dc.datacircle_search_plans(limit=51),
               lambda: dc.datacircle_best_plans("email-finder", limit=0),
               lambda: dc.datacircle_best_plans("email-finder", limit=2.5),
               lambda: dc.datacircle_search_plans(sort="cheapest"),
               lambda: dc.datacircle_search_plans(offset=-1),
               lambda: dc.datacircle_list_apis(limit="many"),
               lambda: dc.datacircle_best_plans(""),
               lambda: dc.datacircle_provider("  ")]
    for call in refused:
        with pytest.raises(DatacircleError):
            call()
    assert [path for path, _, _ in SEEN] == ["/v1/apis/nope/best", "/v1/plans", "/v1/providers/nobody"]


def test_a_429_is_waited_once():
    BUSY.clear()
    SEEN.clear()
    assert dc.datacircle_search_plans(query="busy")["total"] == 1
    assert [path for path, _, _ in SEEN] == ["/v1/plans", "/v1/plans"]


def test_api_out_of_reach():
    before = _api.BASE_URL
    _api.BASE_URL = "http://127.0.0.1:9/v1"
    try:
        with pytest.raises(DatacircleError, match="^Datacircle's API could not be reached"):
            dc.datacircle_list_apis()
    finally:
        _api.BASE_URL = before


def test_the_tools_browser_use_hands_its_model():
    """Tools().functions are the Pydantic AI tools browser-use's Agent gives its model: their arguments checked by their
    schema, their dicts sent as JSON. (A raised DatacircleError reaches the model by browser-use's own hook, tested on
    the live API by a whole Agent run.)"""
    turns = [
        [("datacircle_list_apis", {"query": "email", "limit": 1})],
        [("datacircle_best_plans", {"slug": "email-finder", "limit": "2"}), ("datacircle_search_plans", {"sort": "cheapest"})],
        [("datacircle_search_plans", {"query": "hunter", "sort": "price"}), ("datacircle_provider", {"slug": "Bright Data"}),
         ("datacircle_best_plans", {"slug": "email-finder", "limit": 99})],
    ]

    def scripted(messages, info):
        assert [tool.name for tool in info.function_tools] == OURS
        done = sum(1 for message in messages if isinstance(message, ModelResponse))
        if done < len(turns):
            return ModelResponse(parts=[ToolCallPart(name, args, tool_call_id=f"t{done}{index}")
                                        for index, (name, args) in enumerate(turns[done])])
        return ModelResponse(parts=[TextPart("done")])

    result = Agent(FunctionModel(scripted), tools=datacircle_tools().functions).run_sync("Which email finder API is best?")
    assert result.output == "done"
    parts = {part.tool_call_id: part for message in result.all_messages() for part in getattr(message, "parts", [])
             if isinstance(part, (ToolReturnPart, RetryPromptPart))}
    assert json.loads(parts["t00"].model_response_str())["apis"][0]["slug"] == "email-finder"
    assert json.loads(parts["t10"].model_response_str())["plans"][0]["provider"] == "Hunter"
    assert retried(parts["t11"]) and "Input should be 'score', 'provider' or 'price'" in read(parts["t11"])
    assert json.loads(parts["t21"].model_response_str())["website"] == "https://brightdata.com"
    assert retried(parts["t22"]) and "less than or equal to 50" in read(parts["t22"])
    assert not any(retried(parts[key]) for key in ["t00", "t10", "t20", "t21"])


def retried(part):
    """An argument the schema refused: a retry prompt, or (Pydantic AI 2) a tool return of outcome 'retried'."""
    return isinstance(part, RetryPromptPart) or getattr(part, "outcome", None) == "retried"


def read(part):
    return part.model_response() if isinstance(part, RetryPromptPart) else part.model_response_str()
