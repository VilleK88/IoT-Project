from datetime import date
from pathlib import Path

DEVLOG_PATH = Path("docs/devlog.md")

print("Write devlog entry.")
print("Finish by typing END on its own line.\n")

lines = []

while True:
    line = input()

    if line.strip() == "END":
        break

    lines.append(line)

entry = "\n".join(lines)

today = date.today().isoformat()

DEVLOG_PATH.parent.mkdir(exist_ok=True)

if not DEVLOG_PATH.exists():
    DEVLOG_PATH.write_text("# Devlog\n\n", encoding="utf-8")

with DEVLOG_PATH.open("a", encoding="utf-8") as file:
    file.write(f"\n## {today}\n")
    file.write(f"{entry}\n")

print("Devlog updated.")