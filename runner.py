import concurrent.futures
import os
import subprocess
import time


def run_tool(tool: dict, target: str) -> tuple[subprocess.CompletedProcess, float]:
    cmd = tool["entrypoint"].split() + target.split()
    start = time.perf_counter()
    result = subprocess.run(cmd, cwd=tool["path"], capture_output=True, text=True, check=False)
    duration = round(time.perf_counter() - start, 2)
    return result, duration


def run_tools(requested_tools: list, requested_urls: list, all_tools: dict) -> None:
    if requested_tools:
        selected = []
        for tool_name in requested_tools:
            if tool_name not in all_tools:
                msg = f"Tool not found: {tool_name}"
                raise ValueError(msg)
            selected.append(all_tools[tool_name])
    else:
        selected = list(all_tools.values())

    if not selected or not requested_urls:
        return

    max_workers = min(32, (os.cpu_count() or 1) * 5)
    tasks = [(tool, url) for tool in selected for url in requested_urls]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(lambda pair: run_tool(*pair), tasks)
        for (tool, url), (result, duration) in zip(tasks, results, strict=False):
            header = f"[{tool['name']}]" + (f" {url}" if url else "")
            for line in result.stdout.splitlines():
                print(f"{header} {line}")
            if result.stderr:
                for line in result.stderr.splitlines():
                    print(f"{header} ERROR: {line}")
            print(f"{header} completed in {duration}s")
