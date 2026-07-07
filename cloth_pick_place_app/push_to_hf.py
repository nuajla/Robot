"""
Push a finished cloth pick&place dataset folder to a private Hugging Face
dataset repo (default vhasic/cloth_pickplace_dataset).

Usage:
    python push_to_hf.py                 # push the active dataset folder
    python push_to_hf.py --folder datasets/cloth_pickplace_2026-07-01
    python push_to_hf.py --repo-id vhasic/cloth_pickplace_dataset

The token is read from the .env file (HF_TOKEN). Nothing is uploaded unless
you run this script explicitly.
"""

import argparse
import os

import yaml
from dotenv import load_dotenv
from huggingface_hub import HfApi

import dataset_io

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    load_dotenv(os.path.join(APP_DIR, ".env"))
    with open(os.path.join(APP_DIR, "config.yaml"), "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--folder", default=None,
                    help="dataset folder to push (default: the active/most-recent one)")
    ap.add_argument("--repo-id", default=cfg["huggingface"]["repo_id"])
    ap.add_argument("--public", action="store_true",
                    help="make the repo public (default: private)")
    args = ap.parse_args()

    dataset_io.resolve_local_paths(cfg, APP_DIR)
    folder = args.folder or dataset_io.resolve_dataset_dir(cfg)
    if not os.path.isdir(folder):
        raise SystemExit(f"Dataset folder not found: {folder}")

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN is not set. Put it in the .env file first.")

    private = cfg["huggingface"]["private"] and not args.public
    api = HfApi(token=token)
    api.create_repo(repo_id=args.repo_id, repo_type="dataset", private=private, exist_ok=True)
    api.upload_folder(
        folder_path=folder,
        repo_id=args.repo_id,
        repo_type="dataset",
        commit_message=f"Add/update {os.path.basename(folder)}",
    )
    print(f"Pushed {folder} -> https://huggingface.co/datasets/{args.repo_id}")


if __name__ == "__main__":
    main()
