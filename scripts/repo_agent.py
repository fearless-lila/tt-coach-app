import argparse
from pathlib import Path

from repo_agents.mapper_agent import build_repo_map, get_or_create_repo_map, save_repo_map
from repo_agents.explainer_agent import answer_question






def run_map() -> None:
    root = Path.cwd()
    repo_map = build_repo_map(root)

    print(f"Found {repo_map['file_count']} files across {len(repo_map['areas'])} areas:\n")

    print("Likely entrypoints:")
    for item in repo_map["entrypoints"]:
        print(f"  - {item['path']}: {item['explanation']}")
    print()

    print("Areas:")
    for group_name, group_files in repo_map["areas"].items():
        print(f"{group_name} ({len(group_files)} files)")
        for file_name in group_files[:10]:
            print(f"  - {file_name}")
        if len(group_files) > 10:
            print("  - ...")
        print()

    output_path = save_repo_map(root, repo_map)
    print(f"Saved repo map to {output_path.name}")



def run_ask(question_parts: list[str]) -> None:
    question = " ".join(question_parts).strip()

    if not question:
        print("Please provide a question.")
        print('Example: python scripts/repo_agent.py ask "what is the backend entrypoint?"')
        return

    root = Path.cwd()
    repo_map = get_or_create_repo_map(root)


    print(f"Question: {question}\n")
    print(answer_question(question, root, repo_map))



def main():
    parser = argparse.ArgumentParser(
        description="Repo structure helper"
    )
    parser.add_argument(
        "command",
        choices=["map", "ask"],
        help="Command to run"
    )
    parser.add_argument(
        "query",
        nargs="*",
        help="Question for the ask command"
    )

    args = parser.parse_args()

    if args.command == "map":
        run_map()
    elif args.command == "ask":
        run_ask(args.query)


if __name__ == "__main__":
    main()
