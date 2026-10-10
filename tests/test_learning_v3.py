import importlib.util
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/".opencode/scripts/cbc_learning_v3.py"
spec=importlib.util.spec_from_file_location("cbc_learning_v3",SCRIPT)
v3=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)

class V3Test(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.oldcwd=Path.cwd()
        self.root=Path(self.temp.name)
        os.chdir(self.root)
        self.addCleanup(os.chdir,self.oldcwd)
        self.env=patch.dict(os.environ,{"CBC_LEARNING_HOME":str(self.root/"state")})
        self.env.start();self.addCleanup(self.env.stop)

    def call(self,*args):
        output=io.StringIO();errors=io.StringIO()
        with redirect_stdout(output),redirect_stderr(errors):
            code=v3.main(args)
        return code,output.getvalue(),errors.getvalue()

    def episode(self,n,pattern="preview-fix",outcome="success"):
        status,out,err=self.call("record","--project","CBC","--pattern",pattern,
          "--task",f"Fix situation {n}","--problem",f"Root cause {n}",
          "--lesson",f"Validated solution {n}","--outcome",outcome,"--evidence","Local observation")
        self.assertEqual(status,0,err)
        return out.split()[1]

    def check(self,eid,preset="python-unittest",returncode=0):
        with patch.object(v3,"execute",return_value=(returncode,"a"*64)):
            return self.call("verify","--id",eid,"--preset",preset,"--confirm-run")

    def approve(self,eid):
        return self.call("review","--id",eid,"--decision","approve","--confirm")

    def seed_three(self):
        for i in range(3):
            eid=self.episode(i)
            self.assertEqual(self.check(eid)[0],0)
            self.assertEqual(self.approve(eid)[0],0)

    def draft(self):
        status,output,err=self.call("draft","--project","CBC","--pattern","preview-fix")
        self.assertEqual(status,0,err)
        return output.split()[1]

    def evaluations(self,cid):
        for i in range(3):
            # One baseline failure, three improved-candidate passes. All are run records.
            for variant,code in (("baseline",1 if i==0 else 0),("candidate",0)):
                with patch.object(v3,"execute",return_value=(code,"b"*64)):
                    status,_,err=self.call("evaluate","--candidate",cid,"--variant",variant,
                        "--case-id",f"case-{i}","--preset","python-unittest","--confirm-run")
                self.assertEqual(status,0,err)

    def test_record_deduplicates_and_secret_detection(self):
        one=self.episode(1)
        other=self.episode(1)
        self.assertEqual(one,other)
        self.assertEqual(self.call("record","--project","CBC","--pattern","preview-fix",
           "--task","API key=secret123456","--problem","x","--lesson","x","--outcome","success")[0],2)
        self.assertEqual(self.call("record","--project","CBC","--pattern","../private",
           "--task","t","--problem","p","--lesson","l","--outcome","success")[0],2)
        with v3.database() as db:
            self.assertEqual(db.execute("select count(*) from episodes").fetchone()[0],1)

    def test_approval_requires_real_behavioral_check(self):
        eid=self.episode(0)
        self.assertEqual(self.approve(eid)[0],2)
        self.assertEqual(self.check(eid,"git-diff-check")[0],0)
        self.assertEqual(self.approve(eid)[0],2)
        self.assertEqual(self.check(eid,"python-unittest",1)[0],0)
        self.assertEqual(self.approve(eid)[0],2)
        self.assertEqual(self.check(eid)[0],0)
        self.assertEqual(self.approve(eid)[0],0)
        self.assertEqual(self.approve(eid)[0],2)

    def test_failed_cases_never_approve_and_test_requires_confirm(self):
        eid=self.episode(0,outcome="failed")
        self.assertEqual(self.call("verify","--id",eid,"--preset","python-unittest")[0],2)
        self.assertEqual(self.check(eid)[0],0)
        self.assertEqual(self.approve(eid)[0],2)
        self.assertEqual(self.call("review","--id",eid,"--decision","reject","--confirm")[0],0)

    def test_recall_only_relevant_reviewed_lessons(self):
        eid=self.episode(0)
        self.check(eid)
        self.assertIn("NO_APPROVED",self.call("recall","--project","CBC","--query","Root cause 0")[1])
        self.approve(eid)
        status,out,_=self.call("recall","--project","CBC","--query","Root cause 0")
        self.assertEqual(status,0);self.assertIn("Validated solution 0",out)
        self.assertNotIn("memory.json",out)
        self.assertEqual(self.call("recall","--project","OTHER","--query","Root cause 0")[0],0)

    def test_feedback_duplicates_and_score(self):
        eid=self.episode(0);self.check(eid);self.approve(eid)
        args=("feedback","--id",eid,"--outcome","harmful","--evidence","A later regression appeared")
        self.assertEqual(self.call(*args)[0],0)
        self.assertIn("DUPLICATE_FEEDBACK",self.call(*args)[1])
        with v3.database() as db:
            value,bad=v3.score(db,eid)
            self.assertEqual(bad,1)
            self.assertAlmostEqual(value,1/3)

    def test_draft_requires_three_verified_approved_distinct_tasks(self):
        eid=self.episode(0);self.check(eid);self.approve(eid)
        self.assertEqual(self.call("draft","--project","CBC","--pattern","preview-fix")[0],2)
        self.seed_three()
        cid=self.draft()
        with v3.database() as db:
            c=v3.one(db,"candidates",cid)
            self.assertEqual(c["status"],"draft")
        self.assertFalse((self.root/".opencode/skills/cbc-adaptive-preview-fix/SKILL.md").exists())

    def test_compare_publish_and_versioned_rollback(self):
        self.seed_three()
        first=self.draft()
        self.assertEqual(self.call("publish","--candidate",first,"--confirm")[0],2)
        self.evaluations(first)
        stats=json.loads(self.call("compare","--candidate",first)[1])
        self.assertTrue(stats["eligible"])
        self.assertEqual(self.call("publish","--candidate",first,"--confirm")[0],0)
        path=self.root/".opencode/skills/cbc-adaptive-preview-fix/SKILL.md"
        self.assertIn("Validated solution",path.read_text())
        second=self.draft()
        self.evaluations(second)
        self.assertEqual(self.call("publish","--candidate",second,"--confirm")[0],0)
        self.assertEqual(self.call("rollback","--candidate",first,"--confirm")[0],0)
        with v3.database() as db:
            self.assertEqual(v3.one(db,"candidates",first)["status"],"active")
            self.assertEqual(v3.one(db,"candidates",second)["status"],"retired")

    def test_unowned_skill_never_overwritten(self):
        self.seed_three()
        cid=self.draft();self.evaluations(cid)
        path=self.root/".opencode/skills/cbc-adaptive-preview-fix/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("personal content")
        self.assertEqual(self.call("publish","--candidate",cid,"--confirm")[0],2)
        self.assertEqual(path.read_text(),"personal content")

    def test_migration_dry_run_and_pending_only(self):
        legacy=self.root/"legacy.json"
        legacy.write_text(json.dumps({"lessons":[
          {"project":"CBC","problem":"A real issue","lesson":"A documented historical fix","status":"approved"},
          {"project":"CBC","problem":"sk-abcdefghijklmnopqrst","lesson":"do not copy"}
        ]}))
        self.assertEqual(self.call("migrate","--file",str(legacy))[0],0)
        self.assertFalse(v3.db_file().exists())
        self.assertEqual(self.call("migrate","--file",str(legacy),"--apply")[0],2)
        self.assertEqual(self.call("migrate","--file",str(legacy),"--apply","--confirm")[0],0)
        self.assertEqual(self.call("recall","--project","CBC","--query","documented")[1].strip(),
                         "NO_APPROVED_RELEVANT_LESSONS")
        with v3.database() as db:
            row=db.execute("select review,verified,outcome from episodes").fetchone()
            self.assertEqual(tuple(row),("pending",0,"unknown"))
        self.assertIn("historical fix",legacy.read_text())

    def test_invalid_legacy_and_no_implicit_shell(self):
        legacy=self.root/"bad.json"
        legacy.write_text('{"legacy": "unsupported"}')
        self.assertEqual(self.call("migrate","--file",str(legacy))[0],2)
        self.assertFalse(v3.db_file().exists())
        self.assertEqual(self.call("status")[0],0)
        self.assertIn("episodes 0",self.call("status")[1])

    def test_real_whitelisted_test_preset(self):
        # Real subprocess invocation, in a sandbox with a single tiny unittest.
        (self.root/"tests").mkdir()
        (self.root/"tests"/"test_fixture.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertEqual(2+2,4)\n")
        code,digest=v3.execute("python-unittest",10)
        self.assertEqual(code,0)
        self.assertEqual(len(digest),64)

if __name__=="__main__":
    unittest.main()
