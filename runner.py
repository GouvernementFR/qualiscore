import concurrent.futures
import os
import subprocess
import threading
import time
from subprocess import CompletedProcess


def run_tool(tool: dict, target: str) -> tuple[CompletedProcess, float]:
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

    max_workers = min(32, (os.cpu_count() or 4) * 2)

    def worker_count(tool: dict) -> int:
        return int(tool.get("concurrency_factor", 1) * max_workers)

    semaphores = {tool["name"]: threading.Semaphore(worker_count(tool)) for tool in selected}

    def run_tool_with_limit(tool: dict, target: str) -> tuple[CompletedProcess, float]:
        semaphore = semaphores[tool["name"]]
        with semaphore:
            print(f"Starting {tool['name']} for {target} (max concurrency: {worker_count(tool)})")
            return run_tool(tool, target)

    tasks = [(tool, url) for url in requested_urls for tool in selected]

    print(f"Running {len(tasks)} tasks with up to {max_workers} concurrent workers...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(lambda pair: run_tool_with_limit(pair[0], pair[1]), tasks)
        for (tool, url), (result, duration) in zip(tasks, results, strict=False):
            header = f"[{tool['name']}]" + (f" {url}" if url else "")
            for line in result.stdout.splitlines():
                print(f"{header} {line}")
            if result.stderr:
                for line in result.stderr.splitlines():
                    print(f"{header} ERROR: {line}")
            print(f"{header} completed in {duration}s")
