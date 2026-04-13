import argparse
from pathlib import Path

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
        help="URL target; repeatable",
    )
    parser_run.add_argument(
        "--urls-file",
        "-U",
        help="Path to a text file containing URLs, one per line",
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
        urls = args.url or []
        if args.urls_file:
            urls_file_path = Path(args.urls_file)
            if not urls_file_path.exists():
                parser.error(f"URLs file not found: {args.urls_file}")
            urls.extend(
                [line.strip() for line in urls_file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            )

        if not urls:
            parser.error("At least one URL is required via --url or --urls-file")

        invalid_urls = [url for url in urls if "." not in url]
        if invalid_urls:
            parser.error(f"Invalid URL(s), must contain a dot: {', '.join(invalid_urls)}")

        try:
            run_tools(args.tool, urls, tools)
        except ValueError as exc:
            parser.error(str(exc))
    elif args.command == "report":
        data = discover_data()
        tools = list(tools.keys())
        generate_report(data, tools)
