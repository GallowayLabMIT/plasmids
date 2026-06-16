{{ "=" * title|length }}
{{ title }}
{{ "=" * title|length }}

{{ title }} appears in
{% if links|length == 1%}1 plasmid{% else %}{{ links|length }} plasmids.{% endif %}

{% for name, sublinks in links|groupby("feature_name") %}
- **{{ name }}**
{% for link in sublinks %}
    - :doc:`pKG{{ link.pKG }}: {{ link.plasmid_name }} </plasmids/{{ link.plasmid_uid }}>`
{% endfor %}
{% endfor %}
