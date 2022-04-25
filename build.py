import shutil
import os
import json
import subprocess
import argparse
import sys
from pathlib import Path
import textwrap
import itertools

from typing import List, Dict

from quartzy_parser import get_plasmids, Plasmid, lint_plasmids
parser = argparse.ArgumentParser(description="Generates HTML and PDFs from Markdown files")
parser.add_argument('--force-rebuild', action='store_true')

def plasmid_rst(plasmid: Plasmid) -> str:
    # Process subentries
    plasmid_name = f'pKG{plasmid.pKG} - {plasmid.name}'
    alt_name = '' if plasmid.alt_name is '' else f'**{plasmid.alt_name}**'
    if len(plasmid.errors) > 0:
        errors = '\n.. error::\n' + ''.join(
            [f'\n\t- {entry}' for entry in plasmid.errors]) + '\n'
        plasmid_name = '|fa_error| (E) ' + plasmid_name
    else:
        errors = ''
    if len(plasmid.warnings) > 0:
        warnings = '\n.. warning::\n' + ''.join(
            [f'\n\t- {entry}' for entry in plasmid.warnings]) + '\n'
        plasmid_name = '|fa_warning| (W) ' + plasmid_name
    else:
        warnings = ''
    resistances = ''.join(f'\n- {entry}' for entry in plasmid.resistances)
    plasmid_types = ''.join(f'\n- {entry}' for entry in plasmid.plasmid_type)
    # Generate RST
    return (
        f"{'=' * len(plasmid_name)}\n{plasmid_name}\n{'='*len(plasmid_name)}\n" +
        alt_name + errors + warnings + textwrap.dedent(f'''

        - **Species**: {plasmid.species}
        - **Stock date**: {plasmid.date_stored}

        Resistances
        ~~~~~~~~~~~
        ''') + resistances + textwrap.dedent('''

        Plasmid type
        ~~~~~~~~~~~~
        ''') + plasmid_types +
        '\n\n.. |fa_error| image:: /_static/files/fa_error.svg\n\t\t:width: 20px' +
        '\n\n.. |fa_warning| image:: /_static/files/fa_warning.svg\n\t\t:width: 20px'
    )


def summarize_linting(plasmids:List[Plasmid]) -> str:
    error_map: Dict[str,List[str]] = {}
    warn_map: Dict[str,List[str]] = {}

    for plasmid in plasmids:
        for error_type, _ in plasmid.errors:
            if error_type not in error_map:
                error_map[error_type] = []
            error_map[error_type].append(str(plasmid.pKG))
        for warn_type, _ in plasmid.warnings:
            if warn_type not in error_map:
                warn_map[warn_type] = []
            warn_map[warn_type].append(str(plasmid.pKG))

    n_error_plasmids = len(set(itertools.chain.from_iterable(error_map.values())))
    n_warn_plasmids = len(set(itertools.chain.from_iterable(warn_map.values())))

    if n_error_plasmids == 0:
        error_str = ''
    else:
        error_base = (
            f'.. error::\n\n\tThere are {n_error_plasmids} plasmids with errors.' +
            '\n\n\t.. list-table::\n'
        )

        error_str = error_base
        for error_type, error_plasmids in error_map.items():
            doc_accum = [f':doc:`pKG{pKG} </plasmids/pKG{int(pKG):05d}>`' for pKG in error_plasmids]
            error_str = (
                error_str +
                f'\n\t\t* - {error_type}\n\t\t  - {", ".join(doc_accum)}'
            )

    if n_warn_plasmids == 0:
        warn_str = ''
    else:
        warn_base = (
            f'.. warning::\n\n\tThere are {n_warn_plasmids} plasmids with warnings.' +
            '\n\n\t.. list-table::\n'
        )

        warn_str = warn_base
        for warn_type, warn_plasmids in warn_map.items():
            doc_accum = [f':doc:`pKG{pKG} </plasmids/pKG{int(pKG):05d}>`' for pKG in warn_plasmids]
            warn_str = (
                warn_str +
                f'\n\t\t* - {warn_type}\n\t\t  - {", ".join(doc_accum)}'
            )
    return error_str + '\n' + warn_str

def build_index_page(plasmids: List[Plasmid]) -> str:
    return (textwrap.dedent('''
            .. Galloway Lab plasmids.

            Galloway Lab Plasmids
            ==========================

            ''') + summarize_linting(plasmids) + textwrap.dedent('''
            .. toctree::
                :maxdepth: 1
                :glob:
                :titlesonly:

                plasmids/index
            ''')
    )

if __name__ == '__main__':
    args = parser.parse_args()
    base = Path(__file__).resolve().parent

    if Path(base / 'credentials.json').is_file():
        with open('credentials.json') as cred_file:
            credentials = json.load(cred_file)
    elif 'QUARTZY_USERNAME' in os.environ and 'QUARTZY_PASSWORD' in os.environ:
        credentials = {
            'username': os.environ['QUARTZY_USERNAME'],
            'password': os.environ['QUARTZY_PASSWORD']
        }
    else:
        raise ValueError("Cannot find credentials!")
    plasmids = get_plasmids(credentials['username'], credentials['password'])
    lint_plasmids(plasmids)

    with (base / 'docs' / 'index.rst').open('w', encoding='utf-8') as index_file:
        index_file.write(build_index_page(plasmids))

    plasmid_dir = base / 'docs' / 'plasmids'
    plasmid_dir.mkdir(exist_ok=True)
    for plasmid in plasmids:
        with open(plasmid_dir / f'pKG{plasmid.pKG:05d}.rst', 'w', encoding='utf-8') as f:
            f.write(plasmid_rst(plasmid))




    if args.force_rebuild and (base / 'output').is_dir():
        shutil.rmtree(base / 'output')
    if not (base / 'output').is_dir():
        (base / 'output').mkdir()

    python_exe = sys.executable
    ## Calculate docs path:
    docs_path = base / 'docs'
    html_path = base / 'output' / 'html'
    html_args = [python_exe, '-m', 'sphinx.cmd.build', '-b', 'html', '-j', 'auto', str(docs_path), str(html_path)]
    subprocess.run(html_args)
