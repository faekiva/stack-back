import argparse
import os
import logging

from restic_compose_backup import (
    alerts,
    log,
)
from restic_compose_backup.config import Config
from restic_compose_backup.containers import RunningContainers
from restic_compose_backup.cli_writes import *
from restic_compose_backup.cli_reads import *
from restic_compose_backup import cron, utils
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def main():
    """CLI entrypoint"""
    args, passthroughArgs = parse_args()
    config = Config()
    log.setup(logLevel=args.log_level or config.log_level)
    containers = RunningContainers()

    # Ensure log level is propagated to parent container if overridden
    if args.log_level:
        containers.this_container.set_config_env("LOG_LEVEL", args.log_level)

    if args.action == "status":
        status(config, containers)

    elif args.action == "snapshots":
        snapshots(config, containers)

    elif args.action == "restore":
        restore(config, passthroughArgs)

    elif args.action == "backup":
        backup(config, containers)

    elif args.action == "start-backup-process":
        start_backup_process(config, containers)

    elif args.action == "start-restore-process":
        start_restore_process(config, containers, passthroughArgs)

    elif args.action == "cleanup":
        cleanup(config, containers)

    elif args.action == "alert":
        alert(config, containers)

    elif args.action == "version":
        import restic_compose_backup

        print(restic_compose_backup.__version__)

    elif args.action == "crontab":
        crontab(config)

    elif args.action == "dump-env":
        dump_env()

    elif args.action == "restore":
        restore(config, passthroughArgs)

    # Random test stuff here
    elif args.action == "test":
        nodes = utils.get_swarm_nodes()
        print("Swarm nodes:")
        for node in nodes:
            addr = node.attrs["Status"]["Addr"]
            state = node.attrs["Status"]["State"]
            print(" - {} {} {}".format(node.id, addr, state))


def alert(config, containers: RunningContainers):
    """Test alerts"""
    logger.info("Testing alerts")
    alerts.send(
        subject="{}: Test Alert".format(containers.project_name),
        body="Test message",
    )


def crontab(config):
    """Generate the crontab"""
    print(cron.generate_crontab(config))


def dump_env():
    """Dump all environment variables to a file that can be sourced from cron"""
    print("# This file was generated by stack-back")
    for key, value in os.environ.items():
        print("export {}='{}'".format(key, value))


@dataclass
class Args:
    action: str
    log_level: str | None


def parse_args():
    parser = argparse.ArgumentParser(prog="restic_compose_backup")
    parser.add_argument(
        "action",
        choices=[
            "status",
            "snapshots",
            "backup",
            "start-backup-process",
            "alert",
            "cleanup",
            "version",
            "crontab",
            "dump-env",
            "test",
            "restore",
        ],
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=list(log.LOG_LEVELS.keys()),
        help="Log level",
    )
    known, unknown = parser.parse_known_args()
    return Args(**vars(known)), unknown


if __name__ == "__main__":
    main()
