import argparse
import os
import logging

from restic_compose_backup import (
    alerts,
    backup_runner,
    log,
    restic,
)
from restic_compose_backup.cli_reads import status
from restic_compose_backup.config import Config
from restic_compose_backup.consts import WRITE_PROCESS_CONTAINER_ENV_VAR
from restic_compose_backup.containers import RunningContainers, Container
from restic_compose_backup import cron, utils
from typing import List, Literal

logger = logging.getLogger(__name__)


def backup(
    config,
    containers: RunningContainers,
):
    """Request a backup to start"""
    write(config, containers, "backup")


def restore(
    config: Config,
    containers: RunningContainers,
    passThroughArgs: List[str],
):
    """Request a restore to start"""
    write(config, containers, "restore", passThroughArgs)


def cleanup(config: Config, container: Container):
    """Run forget / prune to minimize storage space"""
    logger.info("Forget outdated snapshots")
    forget_result = restic.forget(
        config.repository,
        config.keep_daily,
        config.keep_weekly,
        config.keep_monthly,
        config.keep_yearly,
    )
    logger.info("Prune stale data freeing storage space")
    prune_result = restic.prune(config.repository)
    return forget_result and prune_result


def write(
    config,
    containers: RunningContainers,
    write_type: Literal["backup", "restore"],
    passThroughArgs: List[str] = [],
):
    # Make sure we don't spawn multiple backup processes
    if containers.write_process_running:
        alerts.send(
            subject=f"Write process container already running",
            body=(
                f"A write process container is already running. \n"
                f"Id: {containers.write_process_container.id}\n"
                f"Name: {containers.write_process_container.name}\n"
            ),
            alert_type="ERROR",
        )
        raise RuntimeError("Write process already running")

    # Map all volumes from the backup container into the backup process container
    volumes = containers.this_container.volumes

    # Map volumes from other containers we are backing up
    mounts = containers.generate_backup_mounts("/volumes")
    volumes.update(mounts)

    logger.debug(
        f"Starting {write_type} container with image %s",
        containers.this_container.image,
    )
    try:
        result = backup_runner.run(
            image=containers.this_container.image,
            command=["rcb", f"start-{write_type}-process", *passThroughArgs],
            volumes=volumes,
            environment=containers.this_container.environment,
            source_container_id=containers.this_container.id,
            labels={
                containers.backup_process_label: "True",
                "com.docker.compose.project": containers.project_name,
            },
        )
    except Exception as ex:
        logger.exception(ex)
        alerts.send(
            subject=f"Exception during {write_type}",
            body=str(ex),
            alert_type="ERROR",
        )
        return

    logger.info(f"{write_type.capitalize()} container exit code: %s", result)

    # Alert the user if something went wrong
    if result != 0:
        alerts.send(
            subject=f"{write_type.capitalize()} process exited with non-zero code",
            body=open("").read(),
            alert_type="ERROR",
        )


def start_backup_process(config, containers: RunningContainers):
    """The actual backup process running inside the spawned container"""
    start_write_process(config, containers, "backup")


def start_restore_process(
    config, containers: RunningContainers, passThroughArgs: List[str]
):
    """The actual restore process running inside the spawned container"""
    start_write_process(config, containers, "restore", passThroughArgs)


# restic.restore(config.repository, passThroughArgs)
def start_write_process(
    config: Config,
    containers: RunningContainers,
    write_type: Literal["backup", "restore"],
    passThroughArgs: List[str] = [],
):
    presentContinuousWriteType = "Backing up" if write_type == "backup" else "Restoring"
    """The actual write process running inside the spawned container"""
    if not utils.is_true(os.environ.get(WRITE_PROCESS_CONTAINER_ENV_VAR)):
        logger.error(
            f"Cannot run {write_type} process in this container. Use {write_type} command instead. "
            "This will spawn a new container with the necessary mounts."
        )
        alerts.send(
            subject=f"Cannot run {write_type} process in this container",
            body=(
                f"Cannot run {write_type} process in this container. Use {write_type} command instead. "
                "This will spawn a new container with the necessary mounts."
            ),
        )
        exit(1)

    status(config, containers)
    errors = False

    # Did we actually get any volumes mounted?
    try:
        has_volumes = os.stat("/volumes") is not None
    except FileNotFoundError:
        logger.warning("Found no volumes to back up")
        has_volumes = False

    # Warn if there is nothing to do
    if len(containers.containers_for_write()) == 0 and not has_volumes:
        logger.error(f"No containers for {write_type} found")
        exit(1)

    # stop containers labeled to stop during backup
    if len(containers.stop_during_backup_containers) > 0:
        utils.stop_containers(containers.stop_during_backup_containers)

    # back up volumes
    if has_volumes:
        try:
            logger.info(f"{presentContinuousWriteType} volumes")
            if write_type == "backup":
                vol_result = restic.backup_files(config.repository, source="/volumes")
            else:
                vol_result = restic.restore(config.repository, passThroughArgs)
            logger.debug("Volume %s exit code: %s", write_type, vol_result)
            if vol_result != 0:
                logger.error(
                    "Volume %s exited with non-zero code: %s", write_type, vol_result
                )
                errors = True
        except Exception as ex:
            logger.error("Exception raised during %s", write_type)
            logger.exception(ex)
            errors = True

    # back up databases
    logger.info(f"{presentContinuousWriteType} databases")
    for container in containers.containers_for_write():
        if container.database_backup_enabled:
            try:
                instance = container.instance
                logger.info(
                    "%s %s in service %s",
                    presentContinuousWriteType,
                    instance.container_type,
                    instance.service_name,
                )
                result = instance.backup()
                logger.debug("Exit code: %s", result)
                if result != 0:
                    logger.error(
                        "%s command exited with non-zero code: %s",
                        write_type.capitalize(),
                        result,
                    )
                    errors = True
            except Exception as ex:
                logger.exception(ex)
                errors = True

    # restart stopped containers after backup
    if len(containers.stop_during_backup_containers) > 0:
        utils.start_containers(containers.stop_during_backup_containers)

    if errors:
        logger.error("Exit code: %s", errors)
        exit(1)

    # Only run cleanup if backup was successful
    if write_type == "backup":
        result = cleanup(config, container)
        logger.debug("cleanup exit code: %s", result)
        if result != 0:
            logger.error("cleanup exit code: %s", result)
            exit(1)

    # Test the repository for errors
    logger.info("Checking the repository for errors")
    check_with_cache = utils.is_true(config.check_with_cache)
    result = restic.check(config.repository, with_cache=check_with_cache)
    if result != 0:
        logger.error("Check exit code: %s", result)
        exit(1)

    logger.info("Backup completed")
