import re
from typing import List, Optional
from .models import Plasmid

def lint_pKG_number(plasmid: Plasmid) -> Optional[str]:
    '''Checks if the item-name pKG number matches the pKG metadata entry.'''
    # Try to extract pKG number
    match = re.match(r'^pKG(?P<pKG>\d+)$', plasmid.q_item_name)
    if match is not None:
        item_name_pKG = int(match['pKG'])
        if item_name_pKG != plasmid.pKG:
            return (f'Item {plasmid.name} has inconsistent pKG numbering.'
                f' Item name: pKG{item_name_pKG}, metadata pKG: pKG{plasmid.pKG}')
    return None

def lint_attachments(plasmid: Plasmid) -> Optional[str]:
    '''Checks if there is at least one attachment'''
    if len(plasmid.attachment_filenames) > 0 or 'no_map' in plasmid.technical_details:
        return None
    return (f"Item {plasmid.name} is missing a plasmid-map attachment! If this is intended, add 'no_map' to Technical Details")

def lint_plasmids(plasmids:List[Plasmid]) -> None:
    '''
    Checks plasmids for consistency. Updates the plasmid list in place with
    lint results.
    '''
    for plasmid in plasmids:
        pKG_lint = lint_pKG_number(plasmid)
        if pKG_lint:
            plasmid.errors.append(('Inconsistent pKG numbers', pKG_lint))
        attachment_lint = lint_attachments(plasmid)
        if attachment_lint:
            plasmid.warnings.append(('Missing plasmid map', attachment_lint))
