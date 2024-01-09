import json
from typing import Literal
from notion_client import Client
import argparse
import logging
import traceback

def setup_parser(argparser: argparse.ArgumentParser) -> None:
    argparser.add_argument('--database', type=str, required=True, help="The notion database to process. This is the chunk of the URL before the after the group name but before the question mark.")
    argparser.add_argument('--field_name', type=str, default="Plasmid Map", help="The field name to update with the body text file")
    argparser.set_defaults(run_func=run)

def move_body_file_to_property(notion: Client, page, prop_name: str) -> Literal["already_present", "updated", "no_body_map", "failed"]:
    # check to see if hte file is currently present
    try:
        if len(page["properties"][prop_name]["files"]) > 0:
            return 'already_present'

        child_blocks = notion.blocks.children.list(page["id"])['results']
        done = False
        for block in child_blocks:
            if 'file' in block:
                to_process = block['file']
                done = True
                break
        if done == False:
            return "no_body_map"
        
        del to_process['caption']
        to_process['file']['url'] = to_process['file']['url'].split("?")[0]

        notion.pages.properties.parent.pages.update(page["id"], properties={prop_name: {"files": [to_process]}})
        return "updated"

    except Exception as e:
        logging.error(f"Unexpected error on {page['id']}:\n{traceback.format_exc()}")
        return "failed"



def run(credentials, args):
    notion = Client(auth=credentials['notion_token'])

    results = notion.databases.query(args.database)
    result_summary = {"already_present": 0, "updated": 0, "no_body_map": 0, "failed": 0}
    for result in results["results"]:
        update_result = move_body_file_to_property(notion, result, args.field_name)
        result_summary[update_result] += 1
    print(f"{result_summary['already_present']} entries already have a map")
    print(f"{result_summary['updated']} entries updated")
    print(f"{result_summary['no_body_map']} entries have no map in their body content")
    print(f"{result_summary['failed']} entries had unknown failures")