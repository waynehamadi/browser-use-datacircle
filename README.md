# browser-use-datacircle

Find the best GTM APIs. We benchmark all the GTM APIs and we put the results on our website.

Our website: https://datacircle.dev

This package gives [browser-use](https://github.com/browser-use/browser-use) four actions that call Datacircle's public API, https://api.datacircle.dev/v1. You need no key and no account. The agent reads our data from the API, not from a page.

| Action | Gives | Call |
| --- | --- | --- |
| `datacircle_list_apis` | Every GTM API on Datacircle, with the API's slug, number of plans, number of providers and best plan | `GET /apis` |
| `datacircle_best_plans` | One API's plans, sorted by score out of 100, best first. Each plan comes with a rank and a price per 1,000 calls | `GET /apis/{slug}/best` |
| `datacircle_search_plans` | Plans that match a provider or plan name, on all APIs or on one API. You can sort them by score, provider or price | `GET /plans` |
| `datacircle_provider` | The APIs a provider sells, and the provider's rank on each API | `GET /providers/{slug}` |

## Install

```bash
pip install browser-use-datacircle
```

The package needs browser-use 1.0 or later and Python 3.11 or later.

## Use the actions in an agent

Give the actions to an agent:

```python
from browser_use import Agent
from browser_use_datacircle import datacircle_tools

agent = Agent("Which email finder API is best for under $5 per 1,000?", tools=datacircle_tools())
print(agent.run_sync().final_result())
```

The agent runs on browser-use's default model and browser. To pick them, pass `llm=` and `browser=` to `Agent`.

To use our actions next to your own, add them to your `Tools`:

```python
from browser_use import Tools
from browser_use_datacircle import add_datacircle_tools

tools = Tools()

@tools.action("Counts the words of a text")
def word_count(text: str) -> int:
    return len(text.split())

add_datacircle_tools(tools)
print([tool.name for tool in tools.functions])
```

Then give that `Tools` to `Agent(task, tools=tools)`.

## Call an action yourself

Each action is a plain function. The function returns our API's answer as a dict:

```python
from browser_use_datacircle import datacircle_best_plans

print(datacircle_best_plans("email-finder", limit=3))
```

## What the model reads

Each action gives the model a JSON object. Each plan comes with a rank, provider, plan, score, price per 1,000 (`perThousand`, in dollars) and a page on datacircle.dev. The page on datacircle.dev lists every field.

You can give a provider's name in place of a slug. The action turns `Bright Data` into `bright-data`.

An unknown slug raises `DatacircleError` with the API's message. For an unknown API slug, the message lists every valid slug. A number out of range also raises `DatacircleError`. browser-use gives the error to the model. The model can then call the action again.

## Network

Each action call makes one HTTPS GET request to https://api.datacircle.dev/v1 and nothing else. The request holds only the action's own arguments. The API takes up to 60 calls a minute from one IP address. When the API asks the action to wait, the action waits up to a minute. The action waits once per call at most. All plans are in one file at https://datacircle.dev/datacircle.json.

## Links

- Datacircle: https://datacircle.dev
- The API: https://datacircle.dev/api
- The API's spec: https://api.datacircle.dev/v1/openapi.json
- What each key means: https://datacircle.dev/fields

MIT license.
