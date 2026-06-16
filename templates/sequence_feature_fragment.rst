{{ title }} appears in
{% if links|length == 1%}1 plasmid{% else %}{{ links|length }} plasmids{% endif %}
under {% if links|groupby("feature_name")|length == 1%}1 name{% else %}{{ links|groupby("feature_name")|length }} names{% endif %}.

{% for name, sublinks in links|groupby("feature_name") %}
- **{{ name }}**
{% for link in sublinks %}
    - :doc:`pKG{{ link.pKG }}: {{ link.plasmid_name }} </plasmids/{{ link.plasmid_uid }}>`
{% endfor %}
{% endfor %}
