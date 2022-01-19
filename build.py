import shutil
import os
import json
import subprocess
import argparse
import sys
from pathlib import Path
import textwrap

from quartzy_parser import get_plasmids, Plasmid
parser = argparse.ArgumentParser(description="Generates HTML and PDFs from Markdown files")
parser.add_argument('--force-rebuild', action='store_true')

def plasmid_rst(plasmid: Plasmid) -> str:
    return textwrap.dedent(f'''
    =============================================================
    pKG{plasmid.pKG} - {plasmid.name}
    =============================================================
    *{plasmid.alt_name}*

    - {plasmid.species}
    - {plasmid.date_stored}

    Resistances
    ~~~~~~~~~~~
    ''').strip() + '\n'.join(plasmid.resistances) + textwrap.dedent('''
    
    Plasmid type
    ~~~~~~~~~~~~
    ''') + '\n'.join(plasmid.plasmid_type)


if __name__ == '__main__':
    args = parser.parse_args()
    base = Path(__file__).resolve().parent

    with open('credentials.json') as cred_file:
        credentials = json.load(cred_file)
    plasmids = get_plasmids(credentials['username'], credentials['password'])

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