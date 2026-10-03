"""Stop hook: write Claude's response text to stuff.txt and taskInfo.txt.

Reads the hook payload (JSON on stdin), walks the session transcript, and dumps
the text of the last assistant turn to <project>/stuff.txt so it can be opened
and read directly with a screen reader instead of hunting through the terminal.
The final message alone (the end-of-task summary) also goes to
<project>/taskInfo.txt, so the summary can be read without scrolling up to it.

The text is lightly reformatted for screen-reader comfort on the way out: bold
markers (**) are stripped, and hyphen bullet markers are swapped for asterisks.
Fenced code blocks are left exactly as written.
"""
import json
import os
import re
import sys
import time


def _screen_reader_friendly(text: str) -> str:
    """Strip ** bold markers and turn '- ' bullets into '* ' bullets, outside
    of fenced code blocks."""
    out = []
    in_fence = False
    fence_re = re.compile(r"^\s*(```|~~~)")
    bullet_re = re.compile(r"^(\s*)-(\s+)")
    for line in text.split("\n"):
        if fence_re.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        line = bullet_re.sub(r"\1*\2", line)
        line = line.replace("**", "")
        out.append(line)
    return "\n".join(out)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    transcript_path = payload.get("transcript_path") or ""

    project_dir = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    out_path = os.path.join(project_dir, "stuff.txt")

    # The summary is the last text block of the turn. Newer Claude Code
    # versions pass it directly in the payload, which is authoritative: the
    # hook can fire before the transcript's final assistant record is flushed
    # to disk, so the transcript alone may be missing it.
    summary = (payload.get("last_assistant_message") or "").strip()

    chunks = _turn_text_chunks(transcript_path)
    if not chunks and not summary:
        # Transcript not flushed yet and no payload text; give it a moment.
        for _ in range(10):
            time.sleep(0.1)
            chunks = _turn_text_chunks(transcript_path)
            if chunks:
                break

    if summary and (not chunks or chunks[-1].strip() != summary):
        chunks.append(summary)
    if not chunks:
        return 0
    summary = summary or chunks[-1].strip()

    _write(os.path.join(project_dir, "taskInfo.txt"),
           _screen_reader_friendly(summary))
    _write(out_path, _screen_reader_friendly("\n\n".join(chunks).strip()))
    return 0


def _turn_text_chunks(transcript_path: str) -> list:
    """Text blocks of the assistant turn after the last genuine user prompt."""
    try:
        raw_lines = open(transcript_path, encoding="utf-8").read().splitlines()
    except Exception:
        return []

    records = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue

    # Find the last genuine user prompt (not a tool_result), skipping sidechains.
    last_user = -1
    for i, rec in enumerate(records):
        if rec.get("type") != "user" or rec.get("isSidechain"):
            continue
        content = rec.get("message", {}).get("content")
        if isinstance(content, str):
            last_user = i
        elif isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "text" for b in content
        ):
            last_user = i

    # Collect assistant text blocks emitted after that prompt.
    chunks = []
    for rec in records[last_user + 1:]:
        if rec.get("type") != "assistant" or rec.get("isSidechain"):
            continue
        content = rec.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "").strip()
                if text:
                    chunks.append(text)
    return chunks


def _write(path: str, text: str) -> None:
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
