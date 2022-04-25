import re
from typing import List, Optional
from .models import Plasmid

def lint_pKG_number(plasmid: Plasmid) -> Optional[str]:
    # Try to extract pKG number
    match = re.match(r'^pKG(?P<pKG>\d+)$', plasmid.q_item_name)
    if match is not None:
        item_name_pKG = int(match['pKG'])
        if item_name_pKG != plasmid.pKG:
            return (f'Item {plasmid.name} has inconsistent pKG numbering.'
                f' Item name: pKG{item_name_pKG}, metadata pKG: pKG{plasmid.pKG}')
    return None

def lint_plasmids(plasmids:List[Plasmid]) -> None:
    '''
    Checks plasmids for consistency. Updates the plasmid list in place with
    lint results.
    '''
    for plasmid in plasmids:
        pKG_lint = lint_pKG_number(plasmid)
        if pKG_lint:
            plasmid.errors.append(('Inconsistent pKG numbers',pKG_lint))
