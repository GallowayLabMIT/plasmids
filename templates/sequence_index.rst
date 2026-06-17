=========
Sequences
=========

.. toctree::
    :maxdepth: 1
    :glob:
    :titlesonly:

    {% for link in links|sort(reverse=true, attribute="n_plasmids") %}
    {{ link.title }} (appears {{ link.n_plasmids }} times) <{{ link.path }}>
    {% endfor %}
