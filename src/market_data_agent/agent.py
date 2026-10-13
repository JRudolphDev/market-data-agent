"""Will operate the loop sequence"""

from market_data_agent.models import TickerMomentumInput

_schema = TickerMomentumInput.model_json_schema()
_schema.pop("description", None)

TOOLS = [
    {
        "name": "summarize_momentum",
        "description": TickerMomentumInput.__doc__,
        "input_schema": _schema,
    }
]
