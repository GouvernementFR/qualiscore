from pathlib import Path

import yaml


def discover_tools() -> dict:
    tools = {}
    for tool_dir in Path("tools").iterdir():
        config_path = tool_dir / "tool.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text())
            config["path"] = str(tool_dir)
            tools[config["name"]] = config
    return tools
