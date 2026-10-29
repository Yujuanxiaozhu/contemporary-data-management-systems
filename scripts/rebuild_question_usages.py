"""Explicit maintenance command; never selects a database from application defaults."""
import argparse
import json
import sys
from pathlib import Path
from bson import ObjectId
from pymongo import MongoClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services import usage


def main():
    p=argparse.ArgumentParser(description='Rebuild one owner scope from authoritative survey sources')
    p.add_argument('--uri',required=True);p.add_argument('--database',required=True)
    p.add_argument('--owner-id',required=True);p.add_argument('--scope',choices=['all','current','historical'],default='all')
    p.add_argument('--apply',action='store_true',required=True)
    args=p.parse_args()
    if args.database in ('admin','local','config') or not ObjectId.is_valid(args.owner_id):p.error('invalid database or owner-id')
    with MongoClient(args.uri,serverSelectionTimeoutMS=3000,tz_aware=True) as client:
        db=client[args.database];uid=ObjectId(args.owner_id)
        if db.users.find_one({'_id':uid},{'_id':1}) is None:p.error('owner not found')
        result=usage.rebuild(db,{'_id':uid},args.scope)
        print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
