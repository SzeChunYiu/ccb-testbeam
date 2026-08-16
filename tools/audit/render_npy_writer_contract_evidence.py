from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape


def render(record: dict[str, object]) -> str:
    checks = record["checks"]
    rows = []
    for index, check in enumerate(checks):
        y = 166 + index * 44
        status = escape(str(check["status"]))
        label = escape(str(check["label"]))
        rows.append(
            f'<text x="58" y="{y}" font-size="20">{label}</text>'
            f'<text x="930" y="{y}" font-size="20" font-weight="bold">{status}</text>'
        )
    height = 230 + len(checks) * 44
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}"
 viewBox="0 0 1200 {height}">
<rect width="1200" height="{height}" fill="white"/>
<text x="52" y="54" font-size="30" font-weight="bold">NPY writer integrity validation</text>
<text x="52" y="90" font-size="19">Policy: {escape(str(record["policy"]))}</text>
<text x="52" y="120" font-size="17">Synthetic software/provenance evidence;
not detector data.</text>
{''.join(rows)}
<text x="52" y="{height - 35}" font-size="17">Focused result:
{escape(str(record["result"]))}</text>
</svg>
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    record = json.loads(args.record.read_text(encoding="utf-8"))
    args.output.write_text(render(record), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
