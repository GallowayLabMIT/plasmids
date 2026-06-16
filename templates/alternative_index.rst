{{ "=" * title|length }}
{{ title }}
{{ "=" * title|length }}

{% include 'lint_summary.rst' %}

{% for plasmid in plasmids %}
- :doc:`{% if plasmid.vendor is not none %}{{ plasmid.vendor }} {% endif %}{{ plasmid.alt_id }} (pKG{{ plasmid.pKG }}) - {{ plasmid.name }} <{{ plasmid.uid }}>`
{% endfor %}
