import asyncio
import logging
import os
import sys

import aiohttp

from asgiref.sync import sync_to_async
from github import Github

REPOSITORY = os.environ["GITHUB_REPOSITORY"]
SHA = os.environ["GITHUB_SHA"]
EVENT = os.environ["GITHUB_EVENT_NAME"]
EVENT_PATH = os.environ["GITHUB_EVENT_PATH"]
TOKEN = os.environ["INPUT_GITHUBTOKEN"]
IGNORECONTEXTS = os.environ["INPUT_IGNORECONTEXTS"].split(',')
IGNOREACTIONS = os.environ["INPUT_IGNOREACTIONS"].split(',')
INTERVAL = float(os.environ["INPUT_CHECKINTERVAL"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def poll_checks(session, repo, ref):
    headers = {
        "Content-Type": "application/vnd.github.antiope-preview+json",
        "Authorization": f"token {TOKEN}",
    }
    url = f"https://api.github.com/repos/{repo}/commits/{ref}/check-runs"

    async with session.get(url, headers=headers, raise_for_status=True) as resp:
        data = await resp.json()

    check_runs = [
        check_run for check_run in data["check_runs"]
        if check_run["name"] not in IGNOREACTIONS
    ]
    logger.info(
        "Checking %s actions: %s",
        len(check_runs),
        ", ".join([check_run["name"] for check_run in check_runs])
    )

    for check_run in check_runs:
        name, status = check_run["name"], check_run["status"]
        logger.info("%s: %s", name, status)
        if status != "completed":
            return False
    return True


async def poll_statuses(commit):
    combined_status = await sync_to_async(commit.get_combined_status)()
    statuses = [
        status for status in combined_status.statuses
        if status.context not in IGNORECONTEXTS
    ]
    logger.info(
        "Checking %s statuses: %s",
        len(statuses),
        ", ".join([status.context for status in statuses])
    )

    for status in statuses:
        context, state = status.context, status.state
        logger.info("%s: %s", context, state)
        if state != "success":
            return False
    return True


async def main():
    g = Github(TOKEN)
    repo = await sync_to_async(g.get_repo)(REPOSITORY)
    commit = await sync_to_async(repo.get_commit)(sha=SHA)

    results = [False, False]
    async with aiohttp.ClientSession() as session:
        while False in results:
            results = await asyncio.gather(
                poll_statuses(commit),
                poll_checks(session, REPOSITORY, SHA),
                return_exceptions=False,
            )
            if False in results:
                logger.info("Checking again in %s seconds", INTERVAL)
                await asyncio.sleep(INTERVAL)
    return results


if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("::set-output name=status::success")
    except:
        print("::set-output name=status::failure")
        raise
