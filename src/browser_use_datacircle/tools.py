"""browser-use actions on Datacircle's open API, https://api.datacircle.dev/v1: no key, no account.

Each action makes one HTTPS GET and gives the API's answer as a dict, which browser-use sends the model as JSON. A
refusal raises DatacircleError with the API's words, which browser-use gives the model as the action's error, so it
can call again. Each is also a plain function.
"""

import inspect
import urllib.parse
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import Field

from browser_use_datacircle import _api


def _best(plans: Any) -> Optional[Dict[str, Any]]:
    """A provider's best plan on an API: its lowest rank, a plan with no score having none."""
    ranked = sorted(plans, key=lambda plan: plan.get("rank") if isinstance(plan.get("rank"), (int, float)) else float("inf"))
    return _api.brief(ranked[0], ["plan", "score", "perThousand", "page"]) if ranked else None


def datacircle_list_apis(
    query: Annotated[Optional[str], Field(description="Words of the API's name or slug, like 'email' or 'linkedin profile': "
                                                      "the APIs that hold the most of them come first. The sheet's order when left out.")] = None,
    limit: Annotated[Optional[int], Field(ge=1, le=200, description="How many APIs to give, 1 to 200. 20 when left out: "
                                                                    "the sheet has about 160.")] = None,
) -> Dict[str, Any]:
    """Lists the GTM APIs on Datacircle's sheet (https://datacircle.dev), with each API's slug, how many plans and
    providers it has and its best plan. Call it first to find an API's slug. Gives total, the APIs found, and apis, up
    to limit of them."""
    count = _api.whole("limit", limit, 1, 200) or 20
    apis = _api.get("/apis")
    words = [word for word in str(query or "").lower().replace("-", " ").split() if word]
    held = []
    for index, api in enumerate(apis):
        name = f"{api.get('api', '')} {str(api.get('slug', '')).replace('-', ' ')}".lower()
        matched = sum(word in name for word in words)
        if matched or not words:
            held.append((-matched, index, api))
    found = [_api.brief(api, _api.API_KEYS) for _, _, api in sorted(held, key=lambda h: h[:2])]
    return {"total": len(found), "apis": found[:count]}


def datacircle_best_plans(
    slug: Annotated[str, Field(description="The API's slug, like 'email-finder' or 'linkedin-profile', as "
                                           "datacircle_list_apis gives it.")],
    limit: Annotated[Optional[int], Field(ge=1, le=50, description="How many plans to give, 1 to 50. 10 when left out.")] = None,
) -> Dict[str, Any]:
    """Gives an API's plans best first by their score out of 100 on Datacircle's benchmark (https://datacircle.dev),
    each with its rank, provider, plan, $ per 1,000 calls and its page: the best providers of an API. perThousand is a
    plan's price of 1,000 items in dollars, pay the plan's whole price in its currency."""
    made = _api.slug(slug)
    if not made:
        raise _api.DatacircleError("Give an API's slug, like 'email-finder': datacircle_list_apis gives every slug")
    count = _api.whole("limit", limit, 1, 50)
    answer = _api.get(f"/apis/{urllib.parse.quote(made)}/best", {"limit": count})
    return {**answer, "plans": [_api.brief(plan) for plan in answer.get("plans") or []]}


def datacircle_search_plans(
    api: Annotated[Optional[str], Field(description="Only this API's plans: its name or slug, like 'email-finder'. A "
                                                    "provider's name goes in query, never here. Every API when left out.")] = None,
    query: Annotated[Optional[str], Field(description="Words that must all appear in the provider's or plan's name, "
                                                      "like 'bright data'.")] = None,
    sort: Annotated[Optional[Literal["score", "provider", "price"]], Field(
        description="score (best first, the default), provider (A to Z) or price ($ per 1,000, lowest first).")] = None,
    limit: Annotated[Optional[int], Field(ge=1, le=50, description="How many plans to give, 1 to 50. 10 when left out.")] = None,
    offset: Annotated[Optional[int], Field(ge=0, description="How many found plans to skip first. 0 when left out.")] = None,
) -> Dict[str, Any]:
    """Searches every plan on Datacircle's sheet (https://datacircle.dev), or one API's, by provider or plan name,
    sorted by score, provider or price. Gives total, offset and up to limit plans. perThousand is a plan's price of
    1,000 items in dollars, pay the plan's whole price in its currency."""
    order = str(sort).strip().lower() if sort not in (None, "") else None
    if order is not None and order not in ("score", "provider", "price"):
        raise _api.DatacircleError(f"sort must be score, provider or price, not {sort!r}")
    params = {"api": api, "query": query, "sort": order, "limit": _api.whole("limit", limit, 1, 50),
              "offset": _api.whole("offset", offset, 0)}
    answer = _api.get("/plans", params)
    return {**answer, "plans": [_api.brief(plan) for plan in answer.get("plans") or []]}


def datacircle_provider(
    slug: Annotated[str, Field(description="The provider's slug, like 'bright-data', or its name, like 'Bright Data': "
                                           "the name is made a slug.")],
) -> Dict[str, Any]:
    """Gives each API one provider sells and its rank on each on Datacircle's benchmark (https://datacircle.dev), with
    its best plan there."""
    made = _api.slug(slug)
    if not made:
        raise _api.DatacircleError("Give a provider's slug or name, like 'bright-data' or 'Bright Data'")
    answer = _api.get(f"/providers/{urllib.parse.quote(made)}")
    apis = [{**_api.brief(entry, ["api", "slug", "rank", "bestPage"]), "plans": len(entry.get("plans") or []),
             "best": _best(entry.get("plans") or [])} for entry in answer.get("apis") or []]
    return {**answer, "apis": apis}


ACTIONS = [datacircle_list_apis, datacircle_best_plans, datacircle_search_plans, datacircle_provider]


def add_datacircle_tools(tools: Any) -> Any:
    """Registers the four actions on a browser_use.Tools of yours, next to your own @tools.action ones, each with its
    docstring as the description the model reads; gives the same Tools back."""
    for action in ACTIONS:
        tools.action(" ".join(inspect.getdoc(action).split()))(action)
    return tools


def datacircle_tools() -> Any:
    """A new browser_use.Tools holding the four actions, for Agent(task, tools=datacircle_tools())."""
    from browser_use import Tools

    return add_datacircle_tools(Tools())
