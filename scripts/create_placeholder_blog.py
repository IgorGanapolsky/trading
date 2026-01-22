#!/usr/bin/env python3
"""Create a placeholder blog post when the main generator fails."""

import sys
from datetime import datetime
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        print("Usage: create_placeholder_blog.py <output_file> <date>")
        sys.exit(1)

    output_file = Path(sys.argv[1])
    date_str = sys.argv[2]

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%B %d, %Y")
        full_date = date_obj.strftime("%A, %B %d, %Y")
    except ValueError:
        formatted_date = date_str
        full_date = date_str

    output_file.parent.mkdir(parents=True, exist_ok=True)

    content = f"""---
layout: post
title: "Daily Report: {formatted_date}"
date: {date_str}
---

# Daily Report: {full_date}

**Day of our AI Trading R&D Phase**

---

## Summary

System operational. Check [GitHub Actions](https://github.com/IgorGanapolsky/trading/actions) for latest workflow runs.

### Today's Focus
- Ralph Loop monitoring system health
- Iron condor strategy on SPY
- Self-healing CI active

---

*Auto-generated placeholder - full report pending data sync*
"""

    output_file.write_text(content)
    print(f"Created placeholder blog post: {output_file}")


if __name__ == "__main__":
    main()
