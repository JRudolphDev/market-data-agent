"""Will handle the stdin and stdout for model tasks"""

import argparse

import anthropic
from dotenv import load_dotenv

from market_data_agent.agent import run_agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a question.")
    parser.add_argument("question", nargs="*", help="Question to ask")
    args = parser.parse_args()
    message = " ".join(args.question)

    while not message:
        message = input("Ask: ").strip()

    load_dotenv()
    client = anthropic.Anthropic()

    result = run_agent(client, message)
    print(result.answer.headline)


if __name__ == "__main__":
    main()
