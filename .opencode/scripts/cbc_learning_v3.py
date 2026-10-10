#!/usr/bin/env python3
"""CBC Learning V3: verified, review-gated, local OpenCode skill evolution."""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SLUG = re.compile(r"^[a-z][a-z0-9-]{2,48}$")
PROJECT = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,48}$")
SECRET = re.compile(
    r"(?:nvapi-[\w-]{8,}|sk-[\w-]{12,}|gh[opusr]_[\w-]{12,}|"
    r"AIza[\w-]{18,}|-----BEGIN .*PRIVATE KEY-----|"
    r"Bearer\s+\S+|(?:password|api[\s_-]?key|access[\s_-]?token)\s*[:=]\s*\S+)", re.I)
PRESETS = {
    "python-unittest": ["python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
    "git-diff-check": ["git", "diff", "--check"],
    "npm-test": ["npm", "test"],
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
 id TEXT PRIMARY KEY, project TEXT NOT NULL, pattern TEXT NOT NULL,
 task TEXT NOT NULL, outcome TEXT NOT NULL CHECK(outcome IN ('success','failed','unknown')),
 problem TEXT NOT NULL, lesson TEXT NOT NULL, evidence TEXT NOT NULL,
 fingerprint TEXT NOT NULL UNIQUE, review TEXT NOT NULL DEFAULT 'pending'
 CHECK(review IN ('pending','approved','rejected')),
 verified INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checks (
 id TEXT PRIMARY KEY, episode_id TEXT NOT NULL REFERENCES episodes(id),
 preset TEXT NOT NULL, exit_code INTEGER NOT NULL, output_hash TEXT NOT NULL,
 created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
 id TEXT PRIMARY KEY, episode_id TEXT NOT NULL REFERENCES episodes(id),
 outcome TEXT NOT NULL CHECK(outcome IN ('helpful','harmful','neutral')),
 evidence TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE, created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidates (
 id TEXT PRIMARY KEY, pattern TEXT NOT NULL, project TEXT NOT NULL,
 version INTEGER NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft'
 CHECK(status IN ('draft','active','retired')), created TEXT NOT NULL,
 UNIQUE(project,pattern,version)
);
CREATE TABLE IF NOT EXISTS evaluations (
 candidate_id TEXT NOT NULL REFERENCES candidates(id),
 case_id TEXT NOT NULL, variant TEXT NOT NULL CHECK(variant IN ('baseline','candidate')),
 preset TEXT NOT NULL, exit_code INTEGER NOT NULL, output_hash TEXT NOT NULL,
 created TEXT NOT NULL, PRIMARY KEY(candidate_id,case_id,variant)
);
CREATE INDEX IF NOT EXISTS idx_episodes_lookup ON episodes(project,pattern,review,verified);
CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(project,pattern,status);
"""

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def sha(data):
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

def ident():
    return uuid.uuid4().hex[:16]

def clean(value, field, limit=400, required=True):
    value = str(value or "").strip()
    if (required and not value) or len(value) > limit or "\n" in value or "\r" in value:
        raise ValueError(f"{field}: expected a single line of 1-{limit} characters")
    if SECRET.search(value):
        raise ValueError(f"{field}: suspected credential; do not save secrets")
    return value

def slug(value, field="pattern"):
    if not SLUG.fullmatch(value or ""):
        raise ValueError(f"{field}: use lowercase letters, numbers, hyphens (3-49 characters)")
    return value

def project(value):
    if not PROJECT.fullmatch(value or ""):
        raise ValueError("project: use a simple 2-49 character project name")
    return value

def base():
    local = os.environ.get("CBC_LEARNING_HOME")
    return Path(local).expanduser() if local else Path.cwd() / ".opencode" / "task-state" / "learning-v3"

def db_file():
    return base() / "learning.sqlite3"

@contextmanager
def database():
    home = base()
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(home, 0o700)
    # sqlite files, including WAL/journal, inherit this private umask.
    old_mask = os.umask(0o077)
    try:
        db = sqlite3.connect(str(db_file()), timeout=10)
    finally:
        os.umask(old_mask)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()

def one(db, table, key):
    if table not in ("episodes", "candidates"):
        raise ValueError("Invalid table")
    row = db.execute(f"SELECT * FROM {table} WHERE id=?", (key,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown {table} ID")
    return row

def record(args):
    p, pat = project(args.project), slug(args.pattern)
    task, problem = clean(args.task, "task", 160), clean(args.problem, "problem", 300)
    lesson, evidence = clean(args.lesson, "lesson"), clean(args.evidence, "evidence", 250, required=False)
    fp = sha(json.dumps([p,pat,task,problem,lesson],ensure_ascii=False))
    with database() as db:
        existing = db.execute("SELECT id FROM episodes WHERE fingerprint=?", (fp,)).fetchone()
        if existing:
            print("DUPLICATE",existing["id"])
            return
        eid = ident()
        db.execute("""INSERT INTO episodes
          (id,project,pattern,task,outcome,problem,lesson,evidence,fingerprint,created)
          VALUES(?,?,?,?,?,?,?,?,?,?)""",
          (eid,p,pat,task,args.outcome,problem,lesson,evidence,fp,now()))
    print("PENDING",eid,"(unverified; not recalled)")

def execute(preset, timeout):
    cmd = PRESETS[preset]
    if not (5 <= timeout <= 180):
        raise ValueError("timeout must be between 5 and 180 seconds")
    try:
        result = subprocess.run(cmd, cwd=Path.cwd(), capture_output=True,
                                timeout=timeout, check=False)
        output = result.stdout[:20000] + result.stderr[:20000]
        return result.returncode, hashlib.sha256(output).hexdigest()
    except subprocess.TimeoutExpired as exc:
        raw = (exc.stdout or b"")[:20000] + (exc.stderr or b"")[:20000]
        return 124, hashlib.sha256(raw).hexdigest()
    except FileNotFoundError as exc:
        raise ValueError(f"Missing executable for preset {preset}: {exc.filename}") from exc

def run_check(args):
    if not args.confirm_run:
        raise ValueError("Tests execute project code. Explicit --confirm-run required")
    if args.preset not in PRESETS:
        raise ValueError("Unapproved preset")
    with database() as db:
        episode = one(db,"episodes",args.id)
        if episode["review"] != "pending":
            raise ValueError("Checks on reviewed episodes are locked")
        rc, digest = execute(args.preset,args.timeout)
        db.execute("INSERT INTO checks VALUES(?,?,?,?,?,?)",
                   (ident(), args.id, args.preset, rc, digest, now()))
        # A green test is only evidence for a recorded success, never for a failed experiment.
        # Formatting checks alone do NOT verify a behavioral fix.
        behavioral = args.preset in ("python-unittest", "npm-test")
        db.execute("UPDATE episodes SET verified=? WHERE id=?",
                   (int(rc == 0 and behavioral and episode["outcome"] == "success"), args.id))
    print("CHECK",args.preset,"exit=",rc,"output_sha256=",digest)
    if rc:
        print("Check did not pass; approval remains blocked")
    elif episode["outcome"] != "success":
        print("Successful check did not verify a non-success episode")

def review(args):
    if not args.confirm:
        raise ValueError("Human --confirm required; agents must not self-approve")
    with database() as db:
        row = one(db,"episodes",args.id)
        if row["review"] != "pending":
            raise ValueError("This proposal was already reviewed")
        if args.decision == "approve" and not (row["verified"] and row["outcome"] == "success"):
            raise ValueError("Approval requires a SUCCESS episode with a REAL passing preset test")
        db.execute("UPDATE episodes SET review=? WHERE id=?",("approved" if args.decision=="approve" else "rejected",args.id))
    print(args.decision.upper(),args.id)

def add_feedback(args):
    evidence = clean(args.evidence,"evidence",250)
    with database() as db:
        row = one(db,"episodes",args.id)
        if row["review"] != "approved":
            raise ValueError("Only approved episodes may receive effectiveness feedback")
        fp = sha(json.dumps([args.id,args.outcome,evidence]))
        if db.execute("SELECT 1 FROM feedback WHERE fingerprint=?",(fp,)).fetchone():
            print("DUPLICATE_FEEDBACK")
            return
        db.execute("INSERT INTO feedback VALUES(?,?,?,?,?,?)",
                   (ident(),args.id,args.outcome,evidence,fp,now()))
    print("FEEDBACK_RECORDED",args.outcome)

def score(db, eid):
    rows = db.execute("SELECT outcome FROM feedback WHERE episode_id=?",(eid,)).fetchall()
    h = sum(r["outcome"]=="helpful" for r in rows)
    bad = sum(r["outcome"]=="harmful" for r in rows)
    return (h+1)/(h+bad+2), bad

def recall(args):
    p = project(args.project)
    query = clean(args.query,"query",100,required=False).lower()
    if not 1 <= args.limit <= 5:
        raise ValueError("recall limit must be between 1 and 5")
    with database() as db:
        rows = db.execute("""SELECT * FROM episodes
                            WHERE project=? AND verified=1 AND review='approved'
                            ORDER BY created DESC LIMIT 300""",(p,)).fetchall()
        words = set(re.findall(r"[\w-]{3,}",query))
        scored = []
        for row in rows:
            text = (row["pattern"]+" "+row["task"]+" "+row["problem"]+" "+row["lesson"]).lower()
            overlap = sum(word in text for word in words)
            if words and not overlap:
                continue
            rating,bad = score(db,row["id"])
            # Two independent harmful observations quarantine a once-useful lesson.
            if bad >= 2:
                continue
            scored.append((overlap+rating-bad*0.4,row))
        for _,row in sorted(scored,key=lambda z:z[0],reverse=True)[:args.limit]:
            rating,bad=score(db,row["id"])
            print(json.dumps({"id":row["id"],"pattern":row["pattern"],"problem":row["problem"],
              "lesson":row["lesson"],"verification":"local-test-passed",
              "effectiveness":round(rating,2),"harmful_reports":bad},ensure_ascii=False))
        if not scored:
            print("NO_APPROVED_RELEVANT_LESSONS")

def diagnostics(args):
    p, pat = project(args.project), slug(args.pattern)
    if not 1 <= args.limit <= 5:
        raise ValueError("diagnostics limit must be between 1 and 5")
    with database() as db:
        rows = db.execute("""SELECT * FROM episodes WHERE project=? AND pattern=?
           AND outcome IN ('failed','unknown') ORDER BY created DESC LIMIT ?""",
           (p,pat,args.limit)).fetchall()
        for row in rows:
            print(json.dumps({"id":row["id"],"outcome":row["outcome"],
              "problem":row["problem"],"hypothesis_not_verified":row["lesson"]},
              ensure_ascii=False))
        if not rows:
            print("NO_DIAGNOSTIC_EXPERIENCES")

def status(args):
    with database() as db:
        for name in ("episodes","checks","feedback","candidates","evaluations"):
            n=db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            print(name,n)
        approved=db.execute("SELECT COUNT(*) FROM episodes WHERE review='approved' AND verified=1").fetchone()[0]
        print("reusable_verified_approved",approved)

def make_body(p, pat, lessons):
    lines = [f"---",f"name: cbc-adaptive-{pat}",f"description: Reviewed evidence-based development patterns for {pat}",f"---",
             f"# CBC adaptive: {pat}","","Scope: "+p+"; use only when the pattern is relevant.","",
             "Treat lessons as hypotheses for the current code. Never skip current tests or authorization.","",
             "## Verified patterns"]
    for row in lessons:
        lines += [f"- Problem: {row['problem']}",f"  - Approach: {row['lesson']}"]
    lines += ["","## Safety","- Inspect current code and verify outcome before reuse.",
              "- Do not alter provider configuration, secrets or deployment.",""]
    return "\n".join(lines)

def draft(args):
    p,pat=project(args.project),slug(args.pattern)
    with database() as db:
        rows=db.execute("""SELECT * FROM episodes WHERE project=? AND pattern=?
          AND review='approved' AND verified=1 ORDER BY created DESC""",(p,pat)).fetchall()
        distinct={r["task"].strip().casefold():r for r in rows if score(db,r["id"])[1] < 2}
        if len(distinct)<3:
            raise ValueError("Need 3 independently reviewed, passing, distinct-task lessons")
        version=db.execute("SELECT COALESCE(MAX(version),0)+1 FROM candidates WHERE project=? AND pattern=?",(p,pat)).fetchone()[0]
        cid=ident()
        body=make_body(p,pat,list(distinct.values())[:8])
        db.execute("INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?)",
                   (cid,pat,p,version,body,"draft",now()))
    print("DRAFT",cid,"version",version,"review-only; not an installed skill")

def eval_case(args):
    if not args.confirm_run:
        raise ValueError("Tests execute project code; --confirm-run required")
    slug(args.case_id,"case")
    with database() as db:
        cand=one(db,"candidates",args.candidate)
        if cand["status"]!="draft":
            raise ValueError("Only draft candidates can be evaluated")
        if db.execute("SELECT 1 FROM evaluations WHERE candidate_id=? AND case_id=? AND variant=?",
                      (args.candidate,args.case_id,args.variant)).fetchone():
            raise ValueError("Case/variant already evaluated (choose another case)")
        rc,digest=execute(args.preset,args.timeout)
        db.execute("INSERT INTO evaluations VALUES(?,?,?,?,?,?,?)",
                   (args.candidate,args.case_id,args.variant,args.preset,rc,digest,now()))
    print("EVALUATION",args.variant,args.case_id,"exit=",rc,"output_sha256=",digest)

def comparison(db,cid):
    data=db.execute("SELECT * FROM evaluations WHERE candidate_id=?",(cid,)).fetchall()
    per={}
    for row in data:
        per.setdefault(row["case_id"],{})[row["variant"]]=row
    paired=[v for v in per.values() if len(v)==2 and v["baseline"]["preset"]==v["candidate"]["preset"]]
    wins=sum(x["baseline"]["exit_code"]!=0 and x["candidate"]["exit_code"]==0 for x in paired)
    regress=sum(x["baseline"]["exit_code"]==0 and x["candidate"]["exit_code"]!=0 for x in paired)
    passed=sum(x["candidate"]["exit_code"]==0 for x in paired)
    # Must outperform baseline in reproducible, paired checks; no fake improvement claims.
    return {"paired":len(paired),"wins":wins,"regressions":regress,"candidate_passes":passed,
            "eligible":len(paired)>=3 and wins>=1 and regress==0 and passed>=3}

def compare(args):
    with database() as db:
        one(db,"candidates",args.candidate)
        print(json.dumps(comparison(db,args.candidate)))

def active_path(pattern):
    return Path.cwd()/".opencode"/"skills"/f"cbc-adaptive-{pattern}"/"SKILL.md"

def atomic_file(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=".cbc-learning-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def publish(args):
    if not args.confirm:
        raise ValueError("Explicit human --confirm required")
    with database() as db:
        cand=one(db,"candidates",args.candidate)
        if cand["status"]!="draft":
            raise ValueError("Only draft candidates can be published")
        if not comparison(db,args.candidate)["eligible"]:
            raise ValueError("Candidate needs 3 paired passing cases, >=1 win and 0 regressions")
        old=db.execute("SELECT * FROM candidates WHERE project=? AND pattern=? AND status='active'",
                       (cand["project"],cand["pattern"])).fetchone()
        path=active_path(cand["pattern"])
        if path.exists() and (not old or path.read_text(encoding="utf-8")!=old["body"]):
            raise ValueError("Existing skill not owned by this engine, or edited: refusing overwrite")
        atomic_file(path,cand["body"])
        if old:
            db.execute("UPDATE candidates SET status='retired' WHERE id=?",(old["id"],))
        db.execute("UPDATE candidates SET status='active' WHERE id=?",(args.candidate,))
    print("PUBLISHED",args.candidate,str(path))

def rollback(args):
    if not args.confirm:
        raise ValueError("Explicit human --confirm required")
    with database() as db:
        target=one(db,"candidates",args.candidate)
        if target["status"]!="retired":
            raise ValueError("Rollback target must be a previously active retired version")
        active=db.execute("SELECT * FROM candidates WHERE project=? AND pattern=? AND status='active'",
                          (target["project"],target["pattern"])).fetchone()
        if not active:
            raise ValueError("No active version to roll back from")
        path=active_path(target["pattern"])
        if not path.exists() or path.read_text(encoding="utf-8")!=active["body"]:
            raise ValueError("Current skill changed outside engine: aborting rollback")
        atomic_file(path,target["body"])
        db.execute("UPDATE candidates SET status='retired' WHERE id=?",(active["id"],))
        db.execute("UPDATE candidates SET status='active' WHERE id=?",(target["id"],))
    print("ROLLED_BACK",target["id"])

def legacy_entries(path):
    source=Path(path)
    if source.stat().st_size>2_000_000:
        raise ValueError("Legacy file over 2 MB; refusing oversized import")
    obj=json.loads(source.read_text(encoding="utf-8"))
    if isinstance(obj,list):
        entries=obj
    elif isinstance(obj,dict):
        entries=next((obj[k] for k in ("lessons","entries","records") if isinstance(obj.get(k),list)),None)
    else:
        entries=None
    if entries is None:
        raise ValueError("Unknown legacy format; expected lessons, entries, or records array")
    if len(entries)>1000:
        raise ValueError("Too many legacy records")
    accepted=[]
    for value in entries:
        if not isinstance(value,dict):
            continue
        try:
            accepted.append({
                "project":project(str(value.get("project") or "CBC")),
                "pattern":slug(str(value.get("pattern") or "legacy-reviewed")),
                "task":clean(value.get("task") or value.get("problem"),"task",160),
                "problem":clean(value.get("problem") or value.get("task"),"problem",300),
                "lesson":clean(value.get("lesson") or value.get("solution") or value.get("action"),"lesson"),
                "evidence":clean(value.get("evidence") or "legacy (not reverified)","evidence",250)
            })
        except ValueError:
            continue
    return len(entries),accepted

def migrate(args):
    total,items=legacy_entries(args.file)
    print("MIGRATION_PREVIEW",f"found={total}",f"sanitized={len(items)}",f"skipped={total-len(items)}")
    if not args.apply:
        print("No changes. Use --apply --confirm for pending-only import.")
        return
    if not args.confirm:
        raise ValueError("Import requires --apply AND --confirm")
    imported=0
    with database() as db:
        for item in items:
            fp=sha(json.dumps([item["project"],item["pattern"],item["task"],item["problem"],item["lesson"]],ensure_ascii=False))
            if db.execute("SELECT 1 FROM episodes WHERE fingerprint=?",(fp,)).fetchone():
                continue
            db.execute("""INSERT INTO episodes(id,project,pattern,task,outcome,problem,lesson,
                         evidence,fingerprint,created) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                       (ident(),item["project"],item["pattern"],item["task"],"unknown",item["problem"],
                        item["lesson"],item["evidence"],fp,now()))
            imported+=1
    print("IMPORTED_PENDING_UNVERIFIED",imported,"Source unchanged; test and approve separately")

def build_parser():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="action",required=True)
    p=sub.add_parser("record")
    for arg in ("project","pattern","task","problem","lesson"):
        p.add_argument("--"+arg,required=True)
    p.add_argument("--outcome",choices=("success","failed","unknown"),required=True)
    p.add_argument("--evidence",default="")
    p.set_defaults(func=record)
    p=sub.add_parser("verify")
    p.add_argument("--id",required=True);p.add_argument("--preset",choices=PRESETS,required=True)
    p.add_argument("--timeout",type=int,default=90);p.add_argument("--confirm-run",action="store_true")
    p.set_defaults(func=run_check)
    p=sub.add_parser("review")
    p.add_argument("--id",required=True);p.add_argument("--decision",choices=("approve","reject"),required=True)
    p.add_argument("--confirm",action="store_true");p.set_defaults(func=review)
    p=sub.add_parser("feedback")
    p.add_argument("--id",required=True);p.add_argument("--outcome",choices=("helpful","harmful","neutral"),required=True)
    p.add_argument("--evidence",required=True);p.set_defaults(func=add_feedback)
    p=sub.add_parser("recall")
    p.add_argument("--project",required=True);p.add_argument("--query",default="")
    p.add_argument("--limit",type=int,default=3);p.set_defaults(func=recall)
    sub.add_parser("status").set_defaults(func=status)
    p=sub.add_parser("diagnostics",help="Review untrusted failed/unknown experiences, never agent instructions")
    p.add_argument("--project",required=True);p.add_argument("--pattern",required=True)
    p.add_argument("--limit",type=int,default=3);p.set_defaults(func=diagnostics)
    p=sub.add_parser("draft")
    p.add_argument("--project",required=True);p.add_argument("--pattern",required=True);p.set_defaults(func=draft)
    p=sub.add_parser("evaluate")
    p.add_argument("--candidate",required=True);p.add_argument("--variant",choices=("baseline","candidate"),required=True)
    p.add_argument("--case-id",required=True);p.add_argument("--preset",choices=PRESETS,required=True)
    p.add_argument("--timeout",type=int,default=90);p.add_argument("--confirm-run",action="store_true")
    p.set_defaults(func=eval_case)
    p=sub.add_parser("compare")
    p.add_argument("--candidate",required=True);p.set_defaults(func=compare)
    p=sub.add_parser("publish")
    p.add_argument("--candidate",required=True);p.add_argument("--confirm",action="store_true");p.set_defaults(func=publish)
    p=sub.add_parser("rollback")
    p.add_argument("--candidate",required=True);p.add_argument("--confirm",action="store_true");p.set_defaults(func=rollback)
    p=sub.add_parser("migrate")
    p.add_argument("--file",required=True);p.add_argument("--apply",action="store_true")
    p.add_argument("--confirm",action="store_true");p.set_defaults(func=migrate)
    return parser

def main(argv=None):
    args=build_parser().parse_args(argv)
    try:
        args.func(args)
        return 0
    except (ValueError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        print("CBC_LEARNING_ERROR:",str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
