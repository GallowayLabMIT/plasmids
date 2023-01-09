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

def lint_addgene_alt_names(plasmid: Plasmid) -> Optional[str]:
    '''Checks to see if the Addgene item name is properly set.'''
    if plasmid.vendor is None or plasmid.vendor != 'Addgene':
        return None
    if re.match(r'^\d+$', plasmid.alt_name) is None:
        return f'Plasmid has the Vendor field set to Addgene, but has a suspicious catalog number: {plasmid.alt_name}. The catalog number should just be the Addgene number!'
    return None

def lint_plasmid_name(plasmid: Plasmid) -> Optional[str]:
    '''Checks to make sure the plasmid name is non-empty'''
    if len(plasmid.name) == 0:
        return f'Plasmid has an empty plasmid name field!'
    return None

def lint_attachments(plasmid: Plasmid) -> Optional[str]:
    '''Checks if there is at least one attachment'''
    if len(plasmid.attachment_filenames) > 0 or 'no_map' in plasmid.technical_details:
        return None
    return (f"Plasmid is missing a plasmid-map attachment! If this is intended, add `no_map` to Technical Details")

# Lint antibiotic resistances
def lint_antibiotic(plasmid: Plasmid) -> Optional[str]:
    '''Checks to see that we aren't specifying combination antibiotics or short names'''
    invalid_resistances = ['AMP', 'Kanamycin/chlor', 'Ampicillin /Chloramphenicol', 'KanamycinR', 'Chloramphenicol&Amp', 'Chloramphenicol/Ampicillin', 'Kan', 'Amp']
    for resistance in plasmid.resistances:
        if resistance in invalid_resistances:
            return(f"Plasmid has an invalid (shortened or dual-resistance) antibiotic resistance entry: {resistance}")


def lint_plasmids(plasmids:List[Plasmid]) -> None:
    '''
    Checks plasmids for consistency. Updates the plasmid list in place with
    lint results.
    '''
    for plasmid in plasmids:
        pKG_lint = lint_pKG_number(plasmid)
        if pKG_lint:
            plasmid.errors.append(('Inconsistent pKG numbers', pKG_lint))
        addgene_lint = lint_addgene_alt_names(plasmid)
        if addgene_lint:
            plasmid.errors.append(('Suspicious Addgene catalog number', addgene_lint))
        name_lint = lint_plasmid_name(plasmid)
        if name_lint:
            plasmid.warnings.append(('Empty plasmid name', name_lint))
        attachment_lint = lint_attachments(plasmid)
        if attachment_lint:
            plasmid.warnings.append(('Missing plasmid map', attachment_lint))
        antibiotic_lint = lint_antibiotic(plasmid)
        if antibiotic_lint:
            plasmid.warnings.append(('Deprecated antibiotic resistance', antibiotic_lint))
