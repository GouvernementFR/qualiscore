import argparse

from registry import discover_tools
from runner import run_tool


def list_tools() -> None:
    tools = discover_tools()
    for name in sorted(tools):
        print(name)


def run_tools(requested_tools, requested_urls) -> None:
    tools = discover_tools()

    if requested_tools:
        selected = []
        for tool_name in requested_tools:
            if tool_name not in tools:
                raise ValueError(f"Tool not found: {tool_name}")
            selected.append(tools[tool_name])
    else:
        selected = list(tools.values())

    if not requested_urls:
        requested_urls = [""]

    for tool in selected:
        for url in requested_urls:
            result = run_tool(tool, url)
            header = f"[{tool['name']}]{' ' + url if url else ''}".strip()
            print(f"{header}: {result.stdout.strip()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Qualiscore CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_list = subparsers.add_parser("list", help="List available tools")

    parser_run = subparsers.add_parser(
        "run",
        help="Run one or more tools",
    )
    parser_run.add_argument(
        "--tool",
        "-t",
        action="append",
        help="Tool name to run; repeatable, defaults to all tools",
    )
    parser_run.add_argument(
        "--url",
        "-u",
        action="append",
        required=True,
        help="URL target; repeatable",
    )

    args = parser.parse_args()

    if args.command == "list":
        list_tools()
    elif args.command == "run":
        try:
            run_tools(args.tool, args.url)
        except ValueError as exc:
            parser.error(str(exc))
