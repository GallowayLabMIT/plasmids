=====================
Galloway Lab Plasmids
=====================

{% include 'lint_summary.rst' %}

.. toctree::
    :maxdepth: 1
    :glob:
    :titlesonly:

    plasmids/index
    {% for alt_index in alt_indexes %}
    plasmids/{{ alt_index }}
    {% endfor %}
