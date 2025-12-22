---
layout: default
title: Lessons Learned
permalink: /lessons/
---

# Lessons Learned

60+ documented failures and fixes from our AI trading journey. Each lesson represents a real problem we encountered and how we solved it.

## All Lessons

{% assign sorted_lessons = site.lessons | sort: 'date' | reverse %}
{% for lesson in sorted_lessons %}
- [{{ lesson.title }}]({{ lesson.url | relative_url }}) {% if lesson.date %}*({{ lesson.date | date: "%b %d, %Y" }})*{% endif %}
{% endfor %}

---

*New lessons are added automatically when we learn from failures.*

[Back to Home]({{ "/" | relative_url }})
