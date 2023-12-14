from typing import List, Dict
from pathlib import Path
import argparse
import os
import json

from . import models
from . import parser
from . import linter

"""
Specify:
- errors, warnings, or both (default)
- specific user(s) or all users (default)
"""

def get_flags(users: List[models.User], plasmids: List[models.Plasmid]):
    
    linter.lint_plasmids(plasmids)
    warnings: Dict[str,List[models.Plasmid]] = {}
    errors: Dict[str,List[models.Plasmid]] = {}

    # Set a default user for plasmids with now-defunct users
    default_user: models.User = None

    # Create a dict of (user_id, User) pairs
    users_by_id: Dict[str,models.User] = {}
    for user in users:
        users_by_id[user.id] = user
        if user.full_name == 'Galloway Lab': default_user = user

    # Loop over all plasmids, storing plasmids with warnings/errors by user
    for plasmid in plasmids:
        if plasmid.owner_id in list(users_by_id.keys()):
            user = users_by_id[plasmid.owner_id].full_name
        else: user = default_user.full_name
        
        if plasmid.warnings:
            if user not in list(warnings.keys()): warnings[user] = [plasmid]
            else: warnings[user].append(plasmid)
        if plasmid.errors: 
            if user not in list(errors.keys()): errors[user] = [plasmid]
            else: errors[user].append(plasmid)

    return warnings, errors

arg_parser = argparse.ArgumentParser(description="Displays plasmids with errors/warnings by user")
group = arg_parser.add_mutually_exclusive_group()
group.add_argument('--only-errors', action='store_true', help='Display only errors')
group.add_argument('--only-warnings', action='store_true', help='Display only warnings')
arg_parser.add_argument('--user', help='Specify user(s) to display, default all')

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
plasmids = parser.get_plasmids(credentials['username'], credentials['password'])
users = []
if not args.user:
    users = all_users
else:
    for u in all_users:
        if u.full_name in args.user: users.append(u)

# Get list of errors/warnings by user
errors, warnings = get_flags(users, plasmids)

# Display errors/warnings
if not args.only_errors:
    print('\nWarnings\n--------\n')
    for user, plasmid_list in errors.items():
        if len(plasmid_list) > 0:
            print(f'{user}:\n  ' + '\n  '.join([str(p.pKG) for p in plasmid_list]) + '\n')
if not args.only_warnings:
    print('Errors\n\n------\n')
    for user, plasmid_list in warnings.items():
        if len(plasmid_list) > 0:
            print(f'{user}:\n  ' + '\n  '.join([str(p.pKG) for p in plasmid_list]) + '\n')