#!/usr/bin/env python3
"""
progress.py — Auto-updates progress bars & percentages in README.md
based on ✅ / 🟡 / ⬜ checkboxes in each course table.

Usage:
    python3 progress.py

Rules:
    ✅ = completed (counts as 1)
    🟡 = in progress (counts as 0.5)
    ⬜ = not started (counts as 0)

It updates:
    - The "Course Dashboard" summary table
    - Each course's "Progress:" line (bar + fraction + %)
    - The "Overall Progress" table
"""

from __future__ import annotations
import re
from datetime import date
from pathlib import Path

README = Path(__file__).parent / "README.md"

DONE, WIP, TODO = "✅", "🟡", "⬜"


def bar(pct: float, blocks: int = 10) -> str:
    """Return a 10-block progress bar like 🟩🟩🟩⬜⬜⬜⬜⬜⬜⬜."""
    filled = round(pct / 100 * blocks)
    return "🟩" * filled + "⬜" * (blocks - filled)


def status_label(pct: float) -> str:
    if pct >= 100:
        return "✅ Completed"
    if pct > 0:
        return "🟡 In Progress"
    return "⬜ Not Started"


def parse_courses(md: str):
    """Find each `## 📘 Course N — Name` section and count ✅/🟡/⬜ in its
    topic table (only inside table rows starting with `| <number> |`)."""
    # split by course headings
    pattern = re.compile(r"^##\s+[^\n]*Course\s+(\d+)\s+[—-]\s+(.+?)\s*$",
                         re.MULTILINE)
    matches = list(pattern.finditer(md))
    courses = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        section = md[start:end]
        num = int(m.group(1))
        name = m.group(2).strip()

        done = wip = todo = 0
        for line in section.splitlines():
            # Only count numbered topic rows: | 1 | Topic | ⬜ | ...
            if re.match(r"^\|\s*\d+\s*\|", line):
                # Take only the first status emoji in the row
                for ch in line:
                    if ch == DONE:
                        done += 1; break
                    if ch == WIP:
                        wip += 1; break
                    if ch == TODO:
                        todo += 1; break
        total = done + wip + todo
        completed_units = done + 0.5 * wip
        pct = (completed_units / total * 100) if total else 0.0
        courses.append({
            "num": num, "name": name,
            "done": done, "wip": wip, "todo": todo,
            "total": total, "pct": pct,
            "section_start": start, "section_end": end,
        })
    return courses


def update_course_progress_lines(md: str, courses):
    """Replace the `**Progress:** ...` line right after each course heading."""
    for c in courses:
        section = md[c["section_start"]:c["section_end"]]
        new_line = (f"**Progress:** `{bar(c['pct'])}` "
                    f"**{c['done']}/{c['total']} ({c['pct']:.0f}%)**")
        new_section, n = re.subn(
            r"\*\*Progress:\*\*\s*`[^`]*`\s*\*\*[^\n]+",
            new_line, section, count=1)
        if n:
            md = md[:c["section_start"]] + new_section + md[c["section_end"]:]
            # recompute offsets for subsequent courses
            delta = len(new_section) - len(section)
            for cc in courses:
                if cc["section_start"] > c["section_start"]:
                    cc["section_start"] += delta
                    cc["section_end"] += delta
            c["section_end"] += delta
    return md


def update_dashboard_table(md: str, courses):
    """Rewrite rows in the Course Dashboard table."""
    lines = md.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        if line.startswith("## 🗂️ Course Dashboard"):
            # copy through header + separator, then rewrite N data rows
            while i + 1 < len(lines) and not lines[i + 1].lstrip().startswith("| #"):
                i += 1
                out.append(lines[i])
            # header
            i += 1; out.append(lines[i])
            # separator
            i += 1; out.append(lines[i])
            # replace data rows
            for c in courses:
                pct = c["pct"]
                row = (f"| {c['num']:<2} | {c['name']:<31} "
                       f"| {c['total']:>6} | {c['done']:>4} "
                       f"| `{bar(pct)}` | {pct:>3.0f}% "
                       f"| {status_label(pct)} |\n")
                out.append(row)
                i += 1  # consume old row
            # skip any remaining old data rows until blank line or non-table
            while i + 1 < len(lines) and lines[i + 1].startswith("|"):
                i += 1
        i += 1
    return "".join(out)


def update_overall(md: str, courses):
    total_topics = sum(c["total"] for c in courses)
    done_topics = sum(c["done"] for c in courses)
    wip_topics = sum(c["wip"] for c in courses)
    units = done_topics + 0.5 * wip_topics
    overall_pct = (units / total_topics * 100) if total_topics else 0.0

    replacements = {
        r"(\*\*Total Courses\*\*\s*\|\s*)[^\|]+": rf"\g<1>{len(courses)}          ",
        r"(\*\*Total Topics\*\*\s*\|\s*)[^\|]+":  rf"\g<1>{total_topics}          ",
        r"(\*\*Topics Done\*\*\s*\|\s*)[^\|]+":   rf"\g<1>{done_topics} / {total_topics}     ",
        r"(\*\*Overall %\*\*\s*\|\s*)[^\|]+":
            rf"\g<1>`{overall_pct:.0f}%` {bar(overall_pct)} ",
        r"(\*\*Last Updated\*\*\s*\|\s*)[^\|]+":  rf"\g<1>{date.today().isoformat()}   ",
    }
    for pat, rep in replacements.items():
        md = re.sub(pat, rep, md)
    return md, overall_pct, done_topics, total_topics


def main():
    md = README.read_text(encoding="utf-8")
    courses = parse_courses(md)
    if not courses:
        print("⚠️  No courses found in README.md")
        return
    md = update_course_progress_lines(md, courses)
    md = update_dashboard_table(md, courses)
    md, overall_pct, done, total = update_overall(md, courses)
    README.write_text(md, encoding="utf-8")

    print(f"✅ Updated README.md")
    print(f"   Overall: {done}/{total} topics ({overall_pct:.1f}%)")
    for c in courses:
        print(f"   • Course {c['num']:>2} {c['name'][:32]:<32} "
              f"{c['done']:>2}/{c['total']:<2}  {c['pct']:>5.1f}%")


if __name__ == "__main__":
    main()
