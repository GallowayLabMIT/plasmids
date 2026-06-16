{# note: this macro strips whitespace with the - operator #}
{# so it is all one line #}
{% macro plasmid_list(plasmids) -%}
    {%- for plasmid in plasmids -%}
    :doc:`pKG{{ plasmid.pKG }} </plasmids/{{ plasmid.uid }}>`
    {%- if not loop.last %}, {% endif -%}
    {%- endfor -%}
{%- endmacro %}

{% if lint_errors|length > 0 %}
.. error::

    {% if n_plasmid_errors == 1 %}
    There is one plasmid with an error.
    {% else %}
    There are {{ n_plasmid_errors }} plasmids with errors.
    {% endif %}

    .. list-table::
        {% for type, plasmids in lint_errors.items() %}
        * - {{ type }}
          - {{ plasmid_list(plasmids) }}
        {% endfor %}

{% endif %}

{% if lint_warnings|length > 0 %}
.. warning::

    {% if n_plasmid_warnings == 1 %}
    There is one plasmid with a warning.
    {% else %}
    There are {{ n_plasmid_warnings }} plasmids with warnings.
    {% endif %}

    .. list-table::
        {% for type, plasmids in lint_warnings.items() %}
        * - {{ type }}
          - {{ plasmid_list(plasmids) }}
        {% endfor %}

{% endif %}
