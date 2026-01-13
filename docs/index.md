---
layout: home
title: AI Trading Dashboard
---

# AI Trading Dashboard

**Last Updated:** {{ site.time | date: "%Y-%m-%d %H:%M" }}

## Portfolio Status

| Metric | Value |
|--------|-------|
| Strategy | Credit Spreads on F, SOFI, T |
| North Star | $100/day after-tax |
| Current Phase | Paper Trading |

## Quick Links

- [Latest Blog Posts](#posts) - Trading journal and lessons
- [GitHub Repository](https://github.com/IgorGanapolsky/trading)

## Recent Posts

<ul>
  {% for post in site.posts limit:5 %}
    <li>
      <a href="{{ post.url | relative_url }}">{{ post.title }}</a>
      <span class="post-date">{{ post.date | date: "%Y-%m-%d" }}</span>
    </li>
  {% endfor %}
</ul>

---

*Built by Igor Ganapolsky & Claude*
