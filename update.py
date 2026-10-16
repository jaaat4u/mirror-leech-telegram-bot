from sys import exit
from importlib import import_module
from logging import (
    FileHandler,
    StreamHandler,
    INFO,
    basicConfig,
    error as log_error,
    info as log_info,
    getLogger,
    ERROR,
)
from os import path, remove, getenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from subprocess import run as srun
from re import fullmatch
from typing import Dict, Any

getLogger("pymongo").setLevel(ERROR)

if path.exists("log.txt"):
    with open("log.txt", "r+") as f:
        f.truncate(0)

if path.exists("rlog.txt"):
    remove("rlog.txt")

basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)


def load_config() -> Dict[str, Any]:
    """Load configuration from config module or environment variables."""
    try:

        settings = import_module("config")
        return {
            key: value.strip() if isinstance(value, str) else value
            for key, value in vars(settings).items()
            if not key.startswith("__")
        }
    except ModuleNotFoundError:
        log_info("Config module not found, loading from environment variables...")
        return {
            "BOT_TOKEN": getenv("BOT_TOKEN", ""),
            "DATABASE_URL": getenv("DATABASE_URL", ""),
            "DATABASE_NAME": getenv("DATABASE_NAME", "mltb"),
            "UPSTREAM_REPO": getenv("UPSTREAM_REPO", ""),
            "UPSTREAM_BRANCH": getenv("UPSTREAM_BRANCH", "master"),
        }


config_file = load_config()

BOT_TOKEN = config_file.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    log_error("BOT_TOKEN variable is missing! Exiting now")
    exit(1)

BOT_ID = BOT_TOKEN.split(":", 1)[0]

DATABASE_NAME = config_file.get("DATABASE_NAME", "mltb")

if DATABASE_URL := config_file.get("DATABASE_URL", "").strip():
    try:
        conn = MongoClient(DATABASE_URL, server_api=ServerApi("1"))
        db = conn[DATABASE_NAME]
        old_config = db.settings.deployConfig.find_one({"_id": BOT_ID}, {"_id": 0})
        config_dict = db.settings.config.find_one({"_id": BOT_ID})
        if (
            old_config is not None and old_config == config_file or old_config is None
        ) and config_dict is not None:
            config_file["UPSTREAM_REPO"] = config_dict["UPSTREAM_REPO"]
            config_file["UPSTREAM_BRANCH"] = config_dict["UPSTREAM_BRANCH"]
        conn.close()
    except Exception as e:
        log_error(f"Database ERROR: {e}")

UPSTREAM_REPO = config_file.get("UPSTREAM_REPO", "").strip()

UPSTREAM_BRANCH = config_file.get("UPSTREAM_BRANCH", "").strip() or "master"

if UPSTREAM_REPO:
    # The updater is optional. Accept only GitHub remotes and a simple branch
    # name, then invoke git with an argument list (never through a shell).
    valid_https = bool(fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?", UPSTREAM_REPO))
    valid_ssh = bool(fullmatch(r"git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?", UPSTREAM_REPO))
    valid_branch = (
        bool(fullmatch(r"[A-Za-z0-9._/-]+", UPSTREAM_BRANCH))
        and not UPSTREAM_BRANCH.startswith("-")
        and ".." not in UPSTREAM_BRANCH
        and not UPSTREAM_BRANCH.endswith("/")
    )

    if not (valid_https or valid_ssh) or not valid_branch:
        log_error("Updater skipped: UPSTREAM_REPO or UPSTREAM_BRANCH is invalid.")
    else:
        if path.exists(".git"):
            srun(["rm", "-rf", ".git"], check=False)

        commands = [
            ["git", "init", "-q"],
            ["git", "remote", "add", "origin", UPSTREAM_REPO],
            ["git", "fetch", "origin", UPSTREAM_BRANCH, "-q"],
            ["git", "reset", "--hard", f"origin/{UPSTREAM_BRANCH}", "-q"],
        ]
        update_ok = True
        for command in commands:
            result = srun(command, check=False)
            if result.returncode != 0:
                update_ok = False
                break

        if update_ok:
            log_info("Successfully updated with latest commit from UPSTREAM_REPO")
        else:
            log_error("Updater failed; check the configured GitHub repository and branch.")
