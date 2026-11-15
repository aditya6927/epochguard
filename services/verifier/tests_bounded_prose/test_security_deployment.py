"""Prevent a Compose override from silently removing HTTP server admission."""
import json
from pathlib import Path
import re


def test_every_packaged_g_server_has_concurrency_bound():
    root = next((p for p in Path(__file__).resolve().parents
                 if (p / "compose.verify.004g.yaml").exists()), Path("/app/security"))
    compose = (root / "compose.verify.004g.yaml").read_text()
    commands = [json.loads(line) for line in re.findall(r"^\s+command: (\[.*\])$", compose, re.M)
                if '"uvicorn"' in line]
    image = root / "services/verifier/Dockerfile.004g"
    commands.append(json.loads(re.search(r"^CMD (\[.*\])$", image.read_text(), re.M)[1]))
    assert len(commands) == 3
    for command in commands:
        assert command[command.index("--limit-concurrency") + 1] == "32"
        assert "--no-access-log" in command
