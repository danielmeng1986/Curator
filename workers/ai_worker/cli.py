"""Supported AI Worker command line."""
from __future__ import annotations
import argparse
import getpass
import shutil
import sys
import time
import random
from pathlib import Path
from . import config
from .client import CuratorClient,EnrollmentClient,CuratorApiError
from .provider import LlamaCliProvider
from .runtime import WorkerRuntime,payload_data
from .workflow import AnalysisWorkflow

WORKER_KINDS={"album_name_analysis":AnalysisWorkflow}

def parser():
    root=argparse.ArgumentParser(prog="python3 -m workers.ai_worker")
    root.add_argument("--state",type=Path,default=config.DEFAULT_STATE)
    commands=root.add_subparsers(dest="command",required=True)
    enroll=commands.add_parser("enroll",help="Request a dedicated Writer device identity")
    enroll.add_argument("--backend-url",required=True);enroll.add_argument("--device-name",required=True)
    commands.add_parser("status",help="Check delayed Admin approval")
    run=commands.add_parser("run",help="Claim and process Work Items")
    run.add_argument("--worker-kind",required=True,choices=sorted(WORKER_KINDS))
    run.add_argument("--llama-cli",required=True);run.add_argument("--model-root",required=True,type=Path)
    run.add_argument("--mmproj",type=Path);run.add_argument("--once",action="store_true")
    run.add_argument("--wait-seconds",type=int,default=30);run.add_argument("--lease-seconds",type=int,default=300)
    return root

def enroll(args):
    if args.state.exists(): raise ValueError("Worker state already exists; use status or move it aside deliberately.")
    material=config.enrollment_material(args.backend_url,args.device_name)
    proof=getpass.getpass("Registration Proof (input hidden): ")
    response=EnrollmentClient(material["backend_url"]).request(device_name=material["device_name"],device_identity=material["device_identity"],
        registration_proof=proof,token=material["token"],enrollment_proof=material["enrollment_proof"])
    material["registration_uuid"]=payload_data(response)["registration"]["uuid"];material["status"]="PendingApproval";config.save(material,args.state)
    print("Writer access requested. Ask an Administrator to approve this AI Worker, then run status.")

def status(args):
    state=config.load(args.state)
    if state.get("status")=="Approved" and "enrollment_proof" not in state:
        principal=payload_data(CuratorClient(state["backend_url"],state["token"]).principal())["principal"]
        print(f"Registration status: Approved ({principal['role']})");return
    response=EnrollmentClient(state["backend_url"]).status(state["registration_uuid"],state["enrollment_proof"])
    registration=payload_data(response)["registration"];state["status"]=registration["status"]
    if registration["status"]=="Approved":
        principal=payload_data(CuratorClient(state["backend_url"],state["token"]).principal())["principal"]
        if principal.get("role")!="writer":raise ValueError("Approved Worker identity is not Writer.")
        state["role"]="writer";state.pop("enrollment_proof",None)
    config.save(state,args.state);print(f"Registration status: {state['status']}")

def run(args):
    state=config.load(args.state)
    if state.get("status")!="Approved":raise ValueError("Worker registration is not approved; run status first.")
    if not 60<=args.lease_seconds<=3600:raise ValueError("lease-seconds must be from 60 to 3600.")
    if not 0<=args.wait_seconds<=30:raise ValueError("wait-seconds must be from 0 to 30.")
    cli=shutil.which(args.llama_cli) or str(Path(args.llama_cli).expanduser())
    if not Path(cli).is_file():raise ValueError("llama.cpp CLI executable was not found.")
    root=args.model_root.expanduser().resolve()
    if not root.is_dir():raise ValueError("Model root was not found.")
    if args.mmproj and not args.mmproj.expanduser().is_file():raise ValueError("Multimodal projector was not found.")
    client=CuratorClient(state["backend_url"],state["token"])
    principal=payload_data(client.principal())["principal"]
    if principal.get("role")!="writer":raise ValueError("AI Worker requires an approved Writer identity.")
    print(f"Curator AI Worker started for {args.worker_kind}. Waiting for compatible work; press Ctrl-C to stop.")
    failures=0
    try:
        while True:
            try:
                claim=payload_data(client.claim_work(args.worker_kind,args.lease_seconds,0 if args.once else args.wait_seconds)).get("item")
                failures=0
            except CuratorApiError as exc:
                if not exc.transient:raise
                failures+=1;delay=min(30,2**min(failures-1,5))+random.uniform(0,0.5)
                print(f"Backend connection interrupted; retrying in {delay:.1f}s.",file=sys.stderr);time.sleep(delay);continue
            if claim:
                snapshot=claim["configuration_snapshot"];model=(root/snapshot["model_file"]).resolve()
                try:model.relative_to(root)
                except ValueError:
                    client.fail_work(claim["uuid"],"WORKER_CONFIGURATION_INVALID","Configured model escapes model root.")
                    raise ValueError("Configured model escapes model root.")
                if not model.is_file():
                    client.fail_work(claim["uuid"],"WORKER_CONFIGURATION_INVALID",f"Configured model file was not found: {snapshot['model_file']}")
                    raise ValueError(f"Configured model file was not found: {snapshot['model_file']}")
                provider=LlamaCliProvider(cli,str(model),mmproj=str(args.mmproj) if args.mmproj else None)
                WorkerRuntime(client,WORKER_KINDS[args.worker_kind](provider),worker_kind=args.worker_kind,
                    lease_seconds=args.lease_seconds).run_once(claim)
            if args.once:return 0
    except KeyboardInterrupt:
        print("\nCurator AI Worker stopped.");return 0

def main(argv=None):
    args=parser().parse_args(argv)
    try:return {"enroll":enroll,"status":status,"run":run}[args.command](args) or 0
    except Exception as exc:print(f"AI Worker error: {exc}",file=sys.stderr);return 2
