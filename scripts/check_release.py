"""Fail-closed release-manifest preflight. Does not create tags or deploy anything."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


def validate_manifest(manifest, commit):
    errors=[]
    if manifest.get('productionReady') is not True:
        errors.append('Production readiness has not been accepted.')
    if manifest.get('candidateCommit') != commit or not re.fullmatch(r'[0-9a-f]{40}',commit):
        errors.append('Manifest must identify the exact checked-out candidate commit.')
    if not re.fullmatch(r'v\d+\.\d+\.\d+',str(manifest.get('releaseTag',''))):
        errors.append('An explicit production version tag is required.')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',str(manifest.get('imageDigest',''))):
        errors.append('The tested image digest is required.')
    entries=manifest.get('gates',[])
    if not isinstance(entries,list):return errors+['Gate evidence must be a list.']
    ids=[entry.get('id') for entry in entries if isinstance(entry,dict)]
    expected={'G'+str(i) for i in range(8)}
    if set(ids)!=expected or len(ids)!=len(expected):
        errors.append('Exactly one entry for each gate G0 through G7 is required.')
    for entry in entries:
        if not isinstance(entry,dict):
            errors.append('Malformed gate entry.');continue
        evidence=entry.get('evidence')
        if entry.get('status')!='passed' or not isinstance(evidence,list) or not evidence or not all(isinstance(e,str) and e.strip() for e in evidence):
            errors.append(str(entry.get('id','unknown'))+': passed status and linked evidence required.')
    approval=manifest.get('ownerAcceptance',{})
    if not isinstance(approval,dict) or approval.get('candidateCommit')!=commit or not approval.get('acceptedBy') or not approval.get('acceptedAt'):
        errors.append('Recorded owner acceptance of this exact candidate is required.')
    recovery=manifest.get('recovery',{})
    if not isinstance(recovery,dict) or not recovery.get('rpo') or not recovery.get('rto'):
        errors.append('Agreed recovery targets are required.')
    return errors


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=Path('docs/RELEASE_GATES.json'))
    options=parser.parse_args()
    try:
        manifest=json.loads(options.manifest.read_text(encoding='utf-8'))
        if not isinstance(manifest,dict):raise ValueError('Manifest root must be an object.')
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        errors=validate_manifest(manifest,commit)
    except (ValueError,OSError,subprocess.CalledProcessError) as error:
        print('RELEASE BLOCKED: '+str(error),file=sys.stderr);return 1
    if errors:
        print('RELEASE BLOCKED:\n'+'\n'.join('- '+message for message in errors));return 1
    print('Manifest structure passed. Review and verify the linked evidence; this command does not certify it, create a tag, publish an image or deploy.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
