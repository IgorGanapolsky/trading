---
layout: default
title: Lessons Learned
permalink: /lessons/
---

# Lessons Learned

60+ documented failures and fixes from our AI trading journey. Each lesson represents a real problem we encountered and how we solved it.

## All Lessons

{% for lesson in site.lessons %}
- [{{ lesson.title }}]({{ lesson.url | relative_url }})
{% endfor %}

---

*New lessons are added automatically when we learn from failures.*

[Back to Home]({{ "/" | relative_url }})
