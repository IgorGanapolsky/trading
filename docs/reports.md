---
layout: page
title: "Reports"
permalink: /reports/
---

Technical reports and system explainers.

{% assign reports = site.reports | sort: "date" | reverse %}
{% if reports.size > 0 %}
<ul>
  {% for report in reports %}
  <li>
    <a href="{{ report.url | relative_url }}">{{ report.title }}</a>
    <small>({{ report.date | date: "%Y-%m-%d" }})</small>
  </li>
  {% endfor %}
</ul>
{% else %}
_No reports published yet._
{% endif %}
