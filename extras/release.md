# Making a release

- Update version in `setup.py`
- Update version in `docs/conf.py`
- Update version in `restic_compose_backup/__init__.py`
- Build and tag image
- push: `docker push ghcr.io/lawndoc/stack-back:<version>`
- Ensure RTD has new docs published

## Example

When releasing a bugfix version we need to update the
main image as well.

```bash
docker build src --tag ghcr.io/lawndoc/stack-back:0.6
docker build src --tag ghcr.io/lawndoc/stack-back:0.6.0

docker push ghcr.io/lawndoc/stack-back:0.5
docker push ghcr.io/lawndoc/stack-back:0.5.0
```
