"""MkDocs hook: the website's sidebar comes from studio/help/README.md, so there's one list of guides for the app's
Help page, GitHub and the website. Each `## Heading` is a section; each `- [Title](guide.md)` line under it a page."""
import re
from pathlib import Path


def on_config(config):
    nav, section = [{"Home": "README.md"}], None
    for line in (Path(config["docs_dir"]) / "README.md").read_text(encoding="utf-8").splitlines():
        if heading := re.match(r"##\s+(.+)", line):
            section = []
            nav.append({heading[1].strip(): section})
        elif section is not None and (guide := re.match(r"-\s+\[([^\]]+)\]\(([\w-]+\.md)\)", line)):
            section.append({guide[1]: guide[2]})
    config["nav"] = nav
    return config
