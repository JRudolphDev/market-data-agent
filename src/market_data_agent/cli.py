"""Will handle the stdin and stdout for model tasks"""

import argparse
import os
import sys

import anthropic
import pydantic
from dotenv import load_dotenv

from market_data_agent.agent import run_agent
from market_data_agent.models import AgentResponse


def format_response(result: AgentResponse) -> str:
    answer = result.answer
    lines = []
    lines.append(answer.headline)
    lines.append("")

    header = f"{'TICKER':<8}"
    for criterion in answer.criteria:
        header += f"{criterion.upper():<20}"

    lines.append(header.rstrip())

    for row in answer.scan:
        line = f"{row.ticker:<8}"
        for verdict in row.verdicts:
            line += f"{verdict:<20}"
        lines.append(line.rstrip())

        for point in row.key_points:
            lines.append(f"          - {point}")

    if answer.detail:
        lines.append("")
        lines.append(answer.detail)

    if answer.caveats:
        lines.append("")
        lines.append("Caveats:")
        for caveat in answer.caveats:
            lines.append(f"  - {caveat}")

    lines.append("")
    lines.append("Tools used: " + ", ".join(result.tools_used))

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a question.")
    parser.add_argument("question", nargs="*", help="Question to ask")
    args = parser.parse_args()
    message = " ".join(args.question)

    try:
        while not message:
            message = input("Ask: ").strip()

        load_dotenv()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("Error: set ANTHROPIC_API_KEY in .env (see .env.example)", file=sys.stderr)
            sys.exit(1)
        client = anthropic.Anthropic()

        result = run_agent(client, message)
    except anthropic.AuthenticationError:
        print("Error: the API key was rejected. Check ANTHROPIC_API_KEY in .env", file=sys.stderr)
        sys.exit(1)
    except anthropic.RateLimitError:
        print("Error: rate limited, try again shortly", file=sys.stderr)
        sys.exit(1)
    except anthropic.APIConnectionError:
        print("Error: could not reach the API", file=sys.stderr)
        sys.exit(1)
    except anthropic.APIStatusError as e:
        print(f"Error: {e}, try again", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}, try a simpler question", file=sys.stderr)
        sys.exit(1)
    except pydantic.ValidationError:
        print("Error: the answer was malformed, try again", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(1)

    print(format_response(result))


if __name__ == "__main__":
    FIXTURE_DATA = False

    if FIXTURE_DATA:
        from pathlib import Path

        sample = Path(__file__).parents[2] / "tests" / "sample_response.json"
        result = AgentResponse.model_validate_json(sample.read_text())
        print(format_response(result))

    else:
        main()
