"""E03 - prepare and validate the AWS desktop AMI.

Builds the supported import format, computes an immutable source hash, caches the
resulting AMI by hash and refuses a paid launch without the organizer envelope. Live
import and launch are BLOCKED without AWS credentials; the command builders and cache
logic are deterministic and tested.
"""
import json
import shutil
from pathlib import Path

from ridge.artifacts import sha256
from ridge.aws import AwsEnvironmentError

SUPPORTED_FORMATS = ('raw', 'vhd', 'vhdx', 'vmdk')
DEFAULT_DESCRIPTION = 'silent-ridge-desktop'


def convert_command(source, target, fmt='raw'):
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError('Unsupported AWS import format: ' + str(fmt))
    return ['qemu-img', 'convert', '-O', fmt, str(source), str(target)]


def convert(source, target, fmt='raw'):
    if Path(target).exists():
        raise ValueError('Choose a new import image; existing images are never overwritten')
    import subprocess
    subprocess.run(convert_command(source, target, fmt), check=True)
    return target


def import_image_command(bucket, key, region, description=DEFAULT_DESCRIPTION):
    containers = f'Format=raw,UserBucket={{S3Bucket={bucket},S3Key={key}}}'
    return ['aws', 'ec2', 'import-image', '--description', description,
            '--disk-containers', containers, '--region', region]


def import_snapshot_command(bucket, key, region, description=DEFAULT_DESCRIPTION):
    containers = f'Format=raw,UserBucket={{S3Bucket={bucket},S3Key={key}}}'
    return ['aws', 'ec2', 'import-snapshot', '--description', description,
            '--disk-container', containers, '--region', region]


def load_inventory(path):
    path = Path(path)
    if not path.is_file():
        return dict(schema=1, images={})
    inventory = json.loads(path.read_text(encoding='utf-8'))
    if inventory.get('schema') != 1 or not isinstance(inventory.get('images'), dict):
        raise ValueError('Unknown AMI inventory schema')
    return inventory


def find_cached(inventory, digest):
    return inventory['images'].get(digest)


def record(inventory, digest, ami, release, path):
    inventory['images'][digest] = dict(ami=ami, release=release)
    Path(path).write_text(json.dumps(inventory, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def source_digest(image):
    return sha256(Path(image))


def ensure_image(aws, image, bucket, key, region, release, inventory_path):
    if not release:
        raise ValueError('An immutable release identifier is required')
    digest = source_digest(image)
    inventory = load_inventory(inventory_path)
    cached = find_cached(inventory, digest)
    if cached:
        return dict(cached, digest=digest, cached=True)
    result = aws.call(*import_image_command(bucket, key, region))
    ami = result.get('ImageId') or result.get('ImportTaskId')
    if not ami:
        raise ValueError('Import did not return an AMI or import task id')
    record(inventory, digest, ami, release, inventory_path)
    return dict(ami=ami, digest=digest, cached=False, import_pending=True)


def launch_guard(authorized):
    if not authorized:
        raise AwsEnvironmentError('Paid launch requires the organizer authorization envelope')


def stage_private(source, staging, destination):
    source, staging, destination = Path(source), Path(staging), Path(destination)
    if not source.is_file():
        raise ValueError('Source image not found: ' + str(source))
    shutil.copyfile(source, destination)
    return destination
