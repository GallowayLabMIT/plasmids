import argparse
import json
import os
from pathlib import Path
from typing import List, Dict

import models
import parser
#from . import parser
#from .models import Plasmid, User

"""
Specify:
- errors, warnings, or both (default)
- specific user(s) or all users (default)
"""

arg_parser = argparse.ArgumentParser(description="Displays plasmids with errors/warnings by user")
arg_parser.add_argument('--type', help='\'errors\' or \'warnings\' or \'both\' (default)')
arg_parser.add_argument('--user', help='specify user(s) to display, default all')

def __main__():
    args = parser.parse_args()
    base = Path(__file__).resolve().parent

    # Access Quartzy database using locally specified credentials
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
    print("found credentials")
    
    # Parse arguments
    flag_type = args.type
    all_users = parser.get_users(credentials['username'], credentials['password'])
    users = []
    if not args.user:
        users = all_users
    else:
        for u in all_users:
            if u.first_name in args.user: users.append(u)

    # Get list of errors/warnings by user
    errors, warnings = get_flags(users)

    # Display errors/warnings
    if flag_type == 'errors':
        for user, plasmid_list in errors.items():
            print(f'{user.full_name}:\n\t')
            print('\n\t'.join([str(p.pKG) for p in plasmid_list]))
            print('\n')
    elif flag_type == 'warnings':
        for user, plasmid_list in warnings.items():
            print(f'{user.full_name}:\n\t')
            print('\n\t'.join([str(p.pKG) for p in plasmid_list]))
            print('\n')
    else:
        for u in users:
            both_list = errors[u] + warnings[u]
            pKGs = [p.pKG for p in both_list].sort()
            print(f'{user.full_name}:\n\t')
            print('\n\t'.join([str(p) for p in pKGs]))
            print('\n')

def get_flags(users: List[models.User]):
    
    warnings = Dict[models.User,List[models.Plasmid]] = {}
    errors = Dict[models.User,models.Plasmid] = {}

    # Loop over users' plasmids, storing plasmids with warnings/errors
    for user in users:
        warn_list = []
        error_list = []
        for plasmid in user.owned_plasmids:
            if plasmid.warnings: warn_list.append(plasmid)
            if plasmid.errors: error_list.append(plasmid)
        warnings[user] = warn_list
        errors[user] = error_list

    return warnings, errors