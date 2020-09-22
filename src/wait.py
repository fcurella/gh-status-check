import asyncio
import logging
import os
import sys

from asgiref.sync import sync_to_async

from github import Github

REPOSITORY = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GITHUB_TOKEN"]
SHA = os.environ["GITHUB_SHA"]
EVENT = os.environ["GITHUB_EVENT_NAME"]
EVENT_PATH = os.environ["GITHUB_EVENT_PATH"]
IGNORECONTEXTS = os.environ["INPUT_IGNORECONTEXTS"].split(',')
INTERVAL = float(os.environ["INPUT_CHECKINTERVAL"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

    result = False
    while result is False:
        result = await poll_statuses(commit)
        if result is False:
            logger.info("Checking again in %s seconds", INTERVAL)
            await asyncio.sleep(INTERVAL)
    return result


if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("::set-output name=status::success")
    except:
        print("::set-output name=status::failure")
        raise
