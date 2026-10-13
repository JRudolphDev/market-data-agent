"""Will operate the loop sequence"""

import anthropic

from market_data_agent.models import TickerMomentumInput
from market_data_agent.tools import summarize_momentum

MODEL_ID = "claude-sonnet-5-5"
MAX_ITERATIONS = 8

_schema = TickerMomentumInput.model_json_schema()
_schema.pop("description", None)

TOOLS = [
    {
        "name": "summarize_momentum",
        "description": TickerMomentumInput.__doc__,
        "input_schema": _schema,
    }
]

TOOL_REGISTRY = {
    "summarize_momentum": (TickerMomentumInput, summarize_momentum),
}


def run_tool(name: str, tool_input: dict) -> str:
    input_model, func = TOOL_REGISTRY[name]
    args = input_model.model_validate(tool_input)
    report = func(args.tickers, args.period)

    return report.model_dump_json()


def run_agent(client: anthropic.Anthropic, question: str) -> str:
    messages = [{"role": "user", "content": question}]

    for _ in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=512,
            output_config={"effort": "medium"},
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    return block.text

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        content = run_tool(block.name, block.input)
                        is_error = False

                    except Exception as e:
                        content = str(e)
                        is_error = True

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": content,
                            "is_error": is_error,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})

    raise RuntimeError(f"No final answer after {MAX_ITERATIONS} iterations")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    client = anthropic.Anthropic()

    example_question = input("Ask: ")
    print(run_agent(client, question=example_question))
