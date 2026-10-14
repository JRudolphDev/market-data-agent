"""Will operate the loop sequence"""

import anthropic
from pydantic import BaseModel

from market_data_agent.models import (
    AgentResponse,
    FinalAnswer,
    TickerFundamentalInput,
    TickerMomentumInput,
    TickerTechnicalInput,
)
from market_data_agent.tools import summarize_fundamentals, summarize_momentum, summarize_technicals

MODEL_ID = "claude-sonnet-5-5"
MAX_ITERATIONS = 8

TOOL_REGISTRY = {
    "summarize_momentum": (TickerMomentumInput, summarize_momentum),
    "summarize_fundamentals": (TickerFundamentalInput, summarize_fundamentals),
    "summarize_technicals": (TickerTechnicalInput, summarize_technicals),
}


def _tool_definition(name: str, input_model: type[BaseModel]) -> dict:
    schema = input_model.model_json_schema()
    schema.pop("description", None)
    return {
        "name": name,
        "description": input_model.__doc__,
        "input_schema": schema,
    }


TOOLS = [_tool_definition(name, model) for name, (model, _) in TOOL_REGISTRY.items()]

ANSWER_FORMAT = {
    "type": "json_schema",
    "schema": FinalAnswer.model_json_schema(),
}


def run_tool(name: str, tool_input: dict) -> str:
    input_model, func = TOOL_REGISTRY[name]
    args = input_model.model_validate(tool_input)
    kwargs = args.model_dump()
    report = func(**kwargs)  # unpack the kwargs

    return report.model_dump_json()


def run_agent(client: anthropic.Anthropic, question: str) -> AgentResponse:
    messages = [{"role": "user", "content": question}]
    tools_used = []

    for _ in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=16000,
            output_config={"effort": "medium", "format": ANSWER_FORMAT},
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    answer = FinalAnswer.model_validate_json(block.text)
                    return AgentResponse(answer=answer, tools_used=tools_used)
            raise RuntimeError("Claude finished without a text answer")

        elif response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        content = run_tool(block.name, block.input)
                        tools_used.append(block.name)  # record only tools that returned data
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

        else:
            raise RuntimeError(f"Unexpected stop_reason: {response.stop_reason}")

    raise RuntimeError(f"No final answer after {MAX_ITERATIONS} iterations")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    client = anthropic.Anthropic()

    example_question = input("Ask: ")
    print(run_agent(client, question=example_question).model_dump_json(indent=2))
