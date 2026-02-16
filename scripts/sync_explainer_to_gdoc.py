#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class Block:
    kind: Literal["title", "h1", "h2", "h3", "body", "bullet", "numbered", "code"]
    text: str


@dataclass
class BlockRange:
    kind: str
    start: int
    end: int


def extract_doc_id(value: str) -> str:
    value = value.strip()
    if "/document/d/" in value:
        m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", value)
        if m:
            return m.group(1)
    return value


def load_content(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    # Remove markdown front matter for cleaner Google Doc rendering.
    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)
        if len(parts) == 2:
            text = parts[1]
    return text.strip() + "\n"


def parse_markdown_blocks(text: str) -> list[Block]:
    blocks: list[Block] = []
    in_code = False
    code_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            if in_code:
                code_text = "\n".join(code_lines).strip("\n")
                if code_text:
                    blocks.append(Block(kind="code", text=code_text))
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            blocks.append(Block(kind="body", text=""))
            continue
        if line.startswith("# "):
            blocks.append(Block(kind="h1", text=line[2:].strip()))
            continue
        if line.startswith("## "):
            blocks.append(Block(kind="h2", text=line[3:].strip()))
            continue
        if line.startswith("### "):
            blocks.append(Block(kind="h3", text=line[4:].strip()))
            continue
        if re.match(r"^\d+\.\s+", line):
            blocks.append(Block(kind="numbered", text=re.sub(r"^\d+\.\s+", "", line).strip()))
            continue
        if line.startswith("- "):
            blocks.append(Block(kind="bullet", text=line[2:].strip()))
            continue
        blocks.append(Block(kind="body", text=line))

    if code_lines:
        blocks.append(Block(kind="code", text="\n".join(code_lines).strip("\n")))
    return blocks


def compose_doc_text(
    blocks: list[Block],
) -> tuple[str, list[tuple[int, int, str]], list[BlockRange]]:
    """
    Returns text + style spans.
    spans: (start_idx, end_idx, style_key) with Google Docs 1-based indices.
    """
    out: list[str] = []
    spans: list[tuple[int, int, str]] = []
    ranges: list[BlockRange] = []
    cursor = 1

    # Add a visual title banner.
    banner = "TRADING AI SYSTEM EXPLAINER\n"
    out.append(banner)
    spans.append((cursor, cursor + len(banner) - 1, "title"))
    cursor += len(banner)
    subtitle = "Continuous Build -> Test -> Evidence -> Learn Loop\n\n"
    out.append(subtitle)
    spans.append((cursor, cursor + len(subtitle) - 2, "subtitle"))
    cursor += len(subtitle)

    for block in blocks:
        line = block.text
        if block.kind in {"bullet", "numbered"}:
            text = f"{line}\n"
        elif block.kind == "code":
            text = f"{line}\n\n"
        else:
            text = f"{line}\n"
            if block.kind in {"h1", "h2", "h3"}:
                text += "\n"

        out.append(text)
        start = cursor
        cursor += len(text)

        if block.kind in {"h1", "h2", "h3", "code", "body", "bullet", "numbered"} and line:
            # only style non-empty lines
            styled_end = start + len(line) - 1
            spans.append((start, styled_end, block.kind))
            ranges.append(BlockRange(kind=block.kind, start=start, end=styled_end + 1))

    return "".join(out), spans, ranges


def fetch_doc_end_index(service, doc_id: str) -> int:
    doc = service.documents().get(documentId=doc_id).execute()
    body = doc.get("body", {}).get("content", [])
    if not body:
        return 1
    end_idx = 1
    for element in body:
        end_idx = max(end_idx, int(element.get("endIndex", 1)))
    return end_idx


def sync_markdown_to_doc(doc_id: str, markdown_text: str, creds_file: Path) -> None:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/documents"]
    creds = Credentials.from_service_account_file(str(creds_file), scopes=scopes)
    docs = build("docs", "v1", credentials=creds)

    blocks = parse_markdown_blocks(markdown_text)
    doc_text, spans, block_ranges = compose_doc_text(blocks)

    end_index = fetch_doc_end_index(docs, doc_id)
    requests = []
    if end_index > 1:
        requests.append(
            {
                "deleteContentRange": {
                    "range": {
                        "startIndex": 1,
                        "endIndex": end_index - 1,
                    }
                }
            }
        )
    requests.append({"insertText": {"location": {"index": 1}, "text": doc_text}})

    # Apply structured paragraph styles and text styles.
    for start, end, style_key in spans:
        if end < start:
            continue
        rng = {"startIndex": start, "endIndex": end + 1}
        if style_key in {"h1", "h2", "h3"}:
            named = (
                "HEADING_1"
                if style_key == "h1"
                else "HEADING_2"
                if style_key == "h2"
                else "HEADING_3"
            )
            requests.append(
                {
                    "updateParagraphStyle": {
                        "range": rng,
                        "paragraphStyle": {"namedStyleType": named},
                        "fields": "namedStyleType",
                    }
                }
            )
            requests.append(
                {
                    "updateTextStyle": {
                        "range": rng,
                        "textStyle": {
                            "foregroundColor": {
                                "color": {"rgbColor": {"red": 0.10, "green": 0.22, "blue": 0.44}}
                            }
                        },
                        "fields": "foregroundColor",
                    }
                }
            )
        elif style_key == "title":
            requests.append(
                {
                    "updateTextStyle": {
                        "range": rng,
                        "textStyle": {
                            "bold": True,
                            "fontSize": {"magnitude": 20, "unit": "PT"},
                            "foregroundColor": {
                                "color": {"rgbColor": {"red": 0.09, "green": 0.27, "blue": 0.52}}
                            },
                        },
                        "fields": "bold,fontSize,foregroundColor",
                    }
                }
            )
            requests.append(
                {
                    "updateParagraphStyle": {
                        "range": rng,
                        "paragraphStyle": {"alignment": "CENTER"},
                        "fields": "alignment",
                    }
                }
            )
        elif style_key == "subtitle":
            requests.append(
                {
                    "updateTextStyle": {
                        "range": rng,
                        "textStyle": {
                            "italic": True,
                            "foregroundColor": {
                                "color": {"rgbColor": {"red": 0.35, "green": 0.41, "blue": 0.51}}
                            },
                        },
                        "fields": "italic,foregroundColor",
                    }
                }
            )
            requests.append(
                {
                    "updateParagraphStyle": {
                        "range": rng,
                        "paragraphStyle": {"alignment": "CENTER"},
                        "fields": "alignment",
                    }
                }
            )
        elif style_key == "code":
            requests.append(
                {
                    "updateTextStyle": {
                        "range": rng,
                        "textStyle": {
                            "weightedFontFamily": {"fontFamily": "Courier New"},
                            "backgroundColor": {
                                "color": {"rgbColor": {"red": 0.95, "green": 0.95, "blue": 0.95}}
                            },
                        },
                        "fields": "weightedFontFamily,backgroundColor",
                    }
                }
            )
        elif style_key == "body":
            requests.append(
                {
                    "updateParagraphStyle": {
                        "range": rng,
                        "paragraphStyle": {
                            "lineSpacing": 125,
                            "spaceAbove": {"magnitude": 2, "unit": "PT"},
                            "spaceBelow": {"magnitude": 2, "unit": "PT"},
                        },
                        "fields": "lineSpacing,spaceAbove,spaceBelow",
                    }
                }
            )

    # Add bullets and numbering for list lines.
    for br in block_ranges:
        if br.kind == "bullet":
            requests.append(
                {
                    "createParagraphBullets": {
                        "range": {"startIndex": br.start, "endIndex": br.end},
                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                    }
                }
            )
        if br.kind == "numbered":
            requests.append(
                {
                    "createParagraphBullets": {
                        "range": {"startIndex": br.start, "endIndex": br.end},
                        "bulletPreset": "NUMBERED_DECIMAL_ALPHA_ROMAN",
                    }
                }
            )

    docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync system explainer markdown into a Google Doc."
    )
    parser.add_argument(
        "--doc",
        required=True,
        help="Google Doc URL or Doc ID",
    )
    parser.add_argument(
        "--in",
        dest="input_path",
        default="docs/_reports/hackathon-system-explainer.md",
        help="Input markdown path",
    )
    parser.add_argument(
        "--creds",
        default=".secrets/google-service-account.json",
        help="Service account json credentials path",
    )
    args = parser.parse_args()

    input_path = Path(args.input_path)
    creds = Path(args.creds)
    if not input_path.exists():
        print(f"error: input missing -> {input_path}")
        return 2
    if not creds.exists():
        print(f"error: creds missing -> {creds}")
        return 3

    doc_id = extract_doc_id(args.doc)
    content = load_content(input_path)
    sync_markdown_to_doc(doc_id=doc_id, markdown_text=content, creds_file=creds)
    print(f"ok: synced explainer to Google Doc {doc_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
