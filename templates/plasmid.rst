{{ "=" * title|length }}
{{ title }}
{{ "=" * title|length }}

{% if alt_name|length > 0 %}
**{% if vendor is not none %}{{ vendor }} {% endif %}{{ alt_name }}**
{% endif %}

{% if errors|length > 0 %}
.. error::

    {% for error in errors %}
    - {{ error }}
    {% endfor %}

{% endif %}

{% if warnings|length > 0 %}
.. error::

    {% for warn in warnings %}
    - {{ warn }}
    {% endfor %}

{% endif %}

- **Species**: {{ species }}
- **Stock date**: {{ date_stored }}

Resistances
~~~~~~~~~~~
{% for resistance in resistances %}
- {{ resistance }}
{% endfor %}

Plasmid type
~~~~~~~~~~~~
{% for ptype in plasmid_types %}
- {{ ptype }}
{% endfor %}

{# these are in case the plasmid has an error/warning, which gets added to the title #}
.. |fa_error| image:: /_static/files/fa_error.svg
    :width: 20px
.. |fa_warning| image:: /_static/files/fa_warning.svg
    :width: 20px
