import copy
import unittest
from check_release import validate_manifest


class ReleaseManifestTests(unittest.TestCase):
    def manifest(self):
        commit='a'*40
        return {'productionReady':True,'candidateCommit':commit,'releaseTag':'v1.0.0',
                'imageDigest':'sha256:'+'b'*64,'recovery':{'rpo':'agreed target','rto':'agreed target'},
                'ownerAcceptance':{'candidateCommit':commit,'acceptedBy':'Owner','acceptedAt':'2026-10-23T10:00:00Z'},
                'gates':[{'id':'G'+str(i),'status':'passed','evidence':['artifact reference']} for i in range(8)]}

    def test_only_complete_structure_passes(self):
        self.assertEqual(validate_manifest(self.manifest(),'a'*40),[])
        self.assertTrue(validate_manifest({},'a'*40))

    def test_wrong_candidate_and_missing_owner_acceptance_block(self):
        self.assertTrue(validate_manifest(self.manifest(),'c'*40))
        candidate=self.manifest();candidate['ownerAcceptance']={}
        self.assertTrue(validate_manifest(candidate,'a'*40))

    def test_unknown_duplicate_missing_or_unproven_gate_blocks(self):
        for change in ('missing','duplicate','unproven','wrong-id'):
            candidate=self.manifest()
            if change=='missing':candidate['gates'].pop()
            elif change=='duplicate':candidate['gates'].append(copy.deepcopy(candidate['gates'][0]))
            elif change=='unproven':candidate['gates'][1]['evidence']=[]
            else:candidate['gates'][1]['id']='G99'
            self.assertTrue(validate_manifest(candidate,'a'*40),change)

    def test_mutable_image_or_nonproduction_version_block(self):
        for field,value in [('imageDigest','latest'),('releaseTag','v1.0.0-rc.1'),('productionReady',False)]:
            candidate=self.manifest();candidate[field]=value
            self.assertTrue(validate_manifest(candidate,'a'*40))

    def test_malformed_evidence_and_unagreed_recovery_block(self):
        candidate=self.manifest();candidate['gates'][0]['evidence']='not a list';candidate['recovery']={}
        self.assertTrue(validate_manifest(candidate,'a'*40))
