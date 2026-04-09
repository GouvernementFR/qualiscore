from datetime import date
from pathlib import Path

import niquests
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


def discover_data() -> dict:
    data = {}
    for data_file in Path("data").glob("*/*.json"):
        key = data_file.parent.name
        if key not in data:
            data[key] = []
        data[key].append(data_file)
    return data


def retrieve_dsfr_versions() -> dict:
    url = "https://api.github.com/repos/GouvernementFR/dsfr/releases"
    response = niquests.get(url)
    response.raise_for_status()
    releases = response.json()
    versions = {release["tag_name"]: date.fromisoformat(release["published_at"][:10]) for release in releases}

    return {
        "fetched_at": date.today(),
        "versions": versions,
    }
