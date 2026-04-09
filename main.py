import argparse

from registry import discover_data, discover_tools
from report import generate_report
from runner import run_tool


def run_tools(requested_tools: list, requested_urls: list, all_tools: dict) -> None:
    if requested_tools:
        selected = []
        for tool_name in requested_tools:
            if tool_name not in all_tools:
                raise ValueError(f"Tool not found: {tool_name}")
            selected.append(all_tools[tool_name])
    else:
        selected = list(all_tools.values())

    if not requested_urls:
        requested_urls = [""]

    for tool in selected:
        for url in requested_urls:
            result = run_tool(tool, url)
            header = f"[{tool['name']}]{' ' + url if url else ''}".strip()
            print(f"{header}: {result.stdout.strip()}")
            if result.stderr.strip():
                print(f"{header} (stderr): {result.stderr.strip()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Qualiscore CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_list = subparsers.add_parser(
        "list",
        help="List available tools",
    )

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

    parser_report = subparsers.add_parser(
        "report",
        help="Generate a report from collected data",
    )

    args = parser.parse_args()

    tools = discover_tools()
    if args.command == "list":
        for name in sorted(tools):
            print(name)
    elif args.command == "run":
        try:
            run_tools(args.tool, args.url, tools)
        except ValueError as exc:
            parser.error(str(exc))
    elif args.command == "report":
        data = discover_data()
        tools = list(tools.keys())
        generate_report(data, tools)
