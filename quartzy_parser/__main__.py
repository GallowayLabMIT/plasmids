from typing import List, Dict
from pathlib import Path
import argparse
import os
import json

from . import models
from . import parser

"""
Specify:
- errors, warnings, or both (default)
- specific user(s) or all users (default)
"""

def get_flags(users: List[models.User]):
    
    warnings: Dict[str,List[models.Plasmid]] = {}
    errors: Dict[str,models.Plasmid] = {}

    # Loop over users' plasmids, storing plasmids with warnings/errors
    for user in users:
        warn_list = []
        error_list = []
        for plasmid in user.owned_plasmids:
            if plasmid.warnings: warn_list.append(plasmid)
            if plasmid.errors: error_list.append(plasmid)
        warnings[user.full_name] = warn_list
        errors[user.full_name] = error_list

    return warnings, errors

arg_parser = argparse.ArgumentParser(description="Displays plasmids with errors/warnings by user")
arg_parser.add_argument('--errors', action='store_true', help='Display errors')
arg_parser.add_argument('--warnings', action='store_true', help='Display warnings')
arg_parser.add_argument('--user', help='specify user(s) to display, default all')

args = arg_parser.parse_args()

# Access Quartzy database using locally specified credentials
if Path('credentials.json').is_file():
    with open('credentials.json') as cred_file:
        credentials = json.load(cred_file)
elif 'QUARTZY_USERNAME' in os.environ and 'QUARTZY_PASSWORD' in os.environ:
    credentials = {
        'username': os.environ['QUARTZY_USERNAME'],
        'password': os.environ['QUARTZY_PASSWORD']
    }
else:
    arg_parser.exit(1, 'Cannot find credentials! Create a `credentials.json` file that looks like\n{"username": "blah", "password": "blah"}\n')

print("found credentials")

# Parse arguments
all_users = parser.get_users(credentials['username'], credentials['password'])
users = []
if not args.user:
    users = all_users
else:
    for u in all_users:
        if u.first_name in args.user: users.append(u)

# Get list of errors/warnings by user
errors, warnings = get_flags(users)

print(errors)
print(warnings)

# Display errors/warnings
if args.errors:
    for user, plasmid_list in errors.items():
        if len(plasmid_list) > 0:
            print(f'{user}:\n\t')
            print('\n\t'.join([str(p.pKG) for p in plasmid_list]))
            print('\n')
if args.warnings:
    for user, plasmid_list in warnings.items():
        if len(plasmid_list) > 0:
            print(f'{user}:\n\t')
            print('\n\t'.join([str(p.pKG) for p in plasmid_list]))
            print('\n')