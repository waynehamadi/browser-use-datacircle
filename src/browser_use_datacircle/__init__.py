"""browser-use actions on Datacircle's open API (https://api.datacircle.dev/v1), no key: Agent(task, tools=datacircle_tools()),
or add_datacircle_tools(tools) on a Tools of your own."""

from browser_use_datacircle._api import DatacircleError
from browser_use_datacircle.tools import (
    add_datacircle_tools,
    datacircle_best_plans,
    datacircle_list_apis,
    datacircle_provider,
    datacircle_search_plans,
    datacircle_tools,
)

__version__ = "0.1.0"
__all__ = ["DatacircleError", "add_datacircle_tools", "datacircle_best_plans", "datacircle_list_apis", "datacircle_provider",
           "datacircle_search_plans", "datacircle_tools"]
