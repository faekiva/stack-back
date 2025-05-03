from restic_compose_backup import (
    alerts,
    backup_runner,
    cli_writes,
    log,
    restic,
)
from restic_compose_backup.config import Config
from restic_compose_backup.containers import RunningContainers
from restic_compose_backup import cron, utils
from dataclasses import dataclass
from typing import List, Literal
import logging

logger = logging.getLogger(__name__)


def snapshots(config: Config, containers: RunningContainers):
    """Display restic snapshots"""
    stdout, stderr = restic.snapshots(config.repository, last=True)
    for line in stdout.split("\n"):
        print(line)


def status(config, containers: RunningContainers):
    """Outputs the backup config for the compose setup"""
    logger.info("Status for compose project '%s'", containers.project_name)
    logger.info("Repository: '%s'", config.repository)
    logger.info("Backup currently running?: %s", containers.write_process_running)
    logger.info(
        "Include project name in backup path?: %s",
        utils.is_true(config.include_project_name),
    )
    logger.debug(
        "Exclude bind mounts from backups?: %s",
        utils.is_true(config.exclude_bind_mounts),
    )
    logger.debug(
        f"Use cache for integrity check?: {utils.is_true(config.check_with_cache)}"
    )
    logger.info("Checking docker availability")

    utils.list_containers()

    if containers.stale_backup_process_containers:
        utils.remove_containers(containers.stale_backup_process_containers)

    # Check if repository is initialized with restic snapshots
    if not restic.is_initialized(config.repository):
        logger.info("Could not get repository info. Attempting to initialize it.")
        result = restic.init_repo(config.repository)
        if result == 0:
            logger.info("Successfully initialized repository: %s", config.repository)
        else:
            logger.error("Failed to initialize repository")

    logger.info("%s Detected Config %s", "-" * 25, "-" * 25)

    # Start making snapshots
    backup_containers = containers.containers_for_write()
    for container in backup_containers:
        logger.info("service: %s", container.service_name)

        if container.volume_backup_enabled:
            logger.info(f" - stop during backup: {container.stop_during_backup}")
            for mount in container.filter_mounts():
                logger.info(
                    " - volume: %s -> %s",
                    mount.source,
                    container.get_volume_backup_destination(mount, "/volumes"),
                )

        if container.database_backup_enabled:
            instance = container.instance
            ping = instance.ping()
            logger.info(
                " - %s (is_ready=%s) -> %s",
                instance.container_type,
                ping == 0,
                instance.backup_destination_path(),
            )
            if ping != 0:
                logger.error(
                    "Database '%s' in service %s cannot be reached",
                    instance.container_type,
                    container.service_name,
                )

    if len(backup_containers) == 0:
        logger.info("No containers in the project has 'stack-back.*' label")

    logger.info("-" * 67)
