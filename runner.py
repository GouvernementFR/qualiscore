import concurrent.futures
import os
import subprocess
import threading
import time
from subprocess import CompletedProcess


class WeightedSemaphore:
    def __init__(self, value: float):
        self._value = float(value)
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)

    def acquire(self, amount: float) -> None:
        with self._condition:
            while self._value < amount:
                self._condition.wait()
            self._value -= amount

    def release(self, amount: float) -> None:
        with self._condition:
            self._value += amount
            self._condition.notify_all()


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
    shared_capacity = WeightedSemaphore(float(max_workers))

    def run_tool_with_limit(tool: dict, target: str) -> tuple[CompletedProcess, float]:
        concurrency_factor = float(tool.get("concurrency_factor", 1))
        weight = max(0.1, round(1.0 / concurrency_factor, 1))
        shared_capacity.acquire(weight)
        try:
            current_capacity = round(max_workers - shared_capacity._value, 1)
            print(
                f"+ {current_capacity}/{max_workers} running, starting {tool['name']} for {target} (weight: {weight})"
            )
            return run_tool(tool, target)
        finally:
            shared_capacity.release(weight)
            current_capacity = round(max_workers - shared_capacity._value, 1)
            print(
                f"- {current_capacity}/{max_workers} running, finished {tool['name']} for {target} (weight: {weight})"
            )

    tasks = [(tool, url) for url in requested_urls for tool in selected]

    print(f"Running {len(tasks)} tasks with {max_workers} shared workers...")

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
