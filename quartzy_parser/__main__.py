from typing import List, Dict
from pathlib import Path
import argparse
import os
import json

from . import lints_by_user
from . import notion_importer


parser = argparse.ArgumentParser(description="Run automated plasmid database functions")
subparsers = parser.add_subparsers(required=True)

lint_by_user_parser = subparsers.add_parser('userlint', description="Displays plasmids with errors/warnings by user")
lints_by_user.setup_parser(lint_by_user_parser)
notion_importer_parser = subparsers.add_parser('notionimport', description="Imports data into Notion, using already uploaded files")
notion_importer.setup_parser(notion_importer_parser)

# Load credentials
if Path('credentials.json').is_file():
    with open('credentials.json') as cred_file:
        credentials = json.load(cred_file)
elif 'QUARTZY_USERNAME' in os.environ and 'QUARTZY_PASSWORD' in os.environ and 'NOTION_TOKEN' in os.environ:
    credentials = {
        'username': os.environ['QUARTZY_USERNAME'],
        'password': os.environ['QUARTZY_PASSWORD'],
        'notion_token': os.environ['NOTION_TOKEN']
    }
else:
    parser.exit(1, 'Cannot find credentials! Create a `credentials.json` file that looks like\n{"username": "blah", "password": "blah", "notion_token": "blah"}\n')

args = parser.parse_args()
args.run_func(credentials, args)