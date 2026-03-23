import subprocess


def run_tool(tool: dict, target: str):
    cmd = tool["entrypoint"].split() + target.split()
    return subprocess.run(cmd, cwd=tool["path"], capture_output=True, text=True, check=False)
