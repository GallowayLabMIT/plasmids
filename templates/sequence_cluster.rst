{{ "=" * title|length }}
{{ title }}
{{ "=" * title|length }}

There are {{ variants|length }} similar sequences in this cluster.

{% for seq_uid, plot_detail in plot_details.items() %}
.. figure:: images/{{ plot_detail.relative_filename }}

    :ref:`crossref_sequence_{{ seq_uid }}`
    has {{ plot_detail.n_edits }} edit{% if plot_detail.n_edits != 1 %}s{% endif %},
    {{ plot_detail.n_inserts }} insert{% if plot_detail.n_inserts != 1 %}s{% endif %},
    and {{ plot_detail.n_deletes}} delete{% if plot_detail.n_deletes != 1 %}s{% endif %}
    relative to the median sequence.

{% endfor %}


{% for seq_uid,variant in variants.items() %}
{% with title=variant.title, links=variant.links %}

.. _crossref_sequence_{{ seq_uid }}:

{{ title }}
{{ "-" * title|length }}


{% include "sequence_feature_fragment.rst" %}
{% endwith %}

{% endfor %}
