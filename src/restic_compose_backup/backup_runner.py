import logging
import os
from restic_compose_backup import utils
from docker.models.containers import Container as DockerContainer

from restic_compose_backup.consts import WRITE_PROCESS_CONTAINER_ENV_VAR

logger = logging.getLogger(__name__)


def run(
    image: str,
    command: str | list[str],
    volumes: dict = None,
    environment: dict = dict(),
    labels: dict = None,
    source_container_id: str = None,
) -> int:
    logger.info("Starting backup container")
    client = utils.docker_client()

    container: DockerContainer = client.containers.run(
        image,
        command,
        labels=labels,
        # auto_remove=True,  # We remove the container further down
        detach=True,
        environment=environment | {WRITE_PROCESS_CONTAINER_ENV_VAR: "true"},
        volumes=volumes,
        network_mode=f"container:{source_container_id}",  # Reuse original container's network stack.
        working_dir=os.getcwd(),
        tty=True,
    )

    logger.info("Backup process container: %s", container.name)
    log_generator = container.logs(stdout=True, stderr=True, stream=True, follow=True)

    def readlines(stream):
        """Read stream line by line"""
        while True:
            line = ""
            while True:
                try:
                    # Make log streaming work for docker ce 17 and 18.
                    # For some reason strings are returned instead if bytes.
                    data = next(stream)
                    if isinstance(data, bytes):
                        line += data.decode()
                    elif isinstance(data, str):
                        line += data
                    if line.endswith("\n"):
                        break
                except StopIteration:
                    break
            if line:
                yield line.rstrip()
            else:
                break

    with open("write.log", "w") as fd:
        for line in readlines(log_generator):
            fd.write(line)
            fd.write("\n")
            logger.info(line)

    container.wait()
    container.reload()
    logger.debug("Container ExitCode %s", container.attrs["State"]["ExitCode"])
    container.remove()

    return int(container.attrs["State"]["ExitCode"])
