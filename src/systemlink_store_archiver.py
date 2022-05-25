"""National Instruments SystemLink Store Archiver."""

import asyncio
import logging
import os
import shutil
import threading
from datetime import date
from typing import Tuple, Union

import winreg
from salt.exceptions import ArgumentValueError, CommandExecutionError
from systemlink.clientconfig import get_configuration_by_id, HTTP_MASTER_CONFIGURATION_ID
from systemlink.clients.nifile import ApiClient, FilesApi, UploadResponse

log = logging.getLogger(__name__)
MB = 1024 * 1024

NI_INSTALLERS_REG_PATH = "SOFTWARE\\National Instruments\\Common\\Installer"
NI_INSTALLERS_REG_KEY_APP_DATA = "NIPUBAPPDATADIR"

__virtualname__: str = "systemlink_store_archiver"


def __virtual__() -> Union[str, Tuple[bool, str]]:
    """
    During module lazy loading, will return the virtual name of this module.
    :return: The virtual name of this module. On error, return a 2-tuple with
        ``False`` for the first item and the error message for the second.
    """
    return __virtualname__


def archive_to_file_service():
    """Archive the SystemLink Store directory and upload archive to the file service."""
    store_directory = _get_store_directory()
    hostname = __grains__["host"]
    workspace = __grains__["systemlink_workspace"]
    file_name = _create_archive_file_name(hostname)
    archive_path = os.path.join(os.path.dirname(store_directory), ".archive", file_name)

    try:
        log.info(f"Creating archive {archive_path} from directory {store_directory}")
        shutil.make_archive(os.path.splitext(archive_path)[0], "zip", root_dir=store_directory)

        log.info(f"Uploading {archive_path} to SystemLink file service")
        uploaded_file_uri = _get_event_loop().run_until_complete(_sl_upload(archive_path, workspace))
        log.info(f"Uploaded to {uploaded_file_uri}")

        log.info(f"Cleaning store directory {store_directory}")
        _clean_directory(store_directory)
        return uploaded_file_uri
    except Exception as ex:
        raise CommandExecutionError(f"Error while archiving to file service: {type(ex)} - {ex}")
    finally:
        try:
            log.info(f"Removing archive {archive_path}")
            os.remove(archive_path)
        except Exception:
            pass


async def _sl_upload(local_file_path: str, workspace: str) -> str:
    configuration = get_configuration_by_id(HTTP_MASTER_CONFIGURATION_ID, "/nifile", False)
    api_client = ApiClient(configuration=configuration)
    files_api = FilesApi(api_client)
    try:
        upload_response: UploadResponse = await files_api.upload(local_file_path, workspace=workspace)
        return configuration.host.rstrip("/nifile") + upload_response.to_dict()["uri"]
    finally:
        await api_client.close()


def _get_event_loop() -> asyncio.AbstractEventLoop:
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def archive_to_s3(s3_bucket, destination_s3_root, chunk_size_mb=2):
    """
    Archive the SystemLink Store directory and upload archive to the s3 bucket.

    :param s3_bucket: The name of the s3 bucket to upload the archive to
    :param destination_s3_root: The root of the object ID to give to to the uploaded archive
    :param chunk_size_mb: The size in MB to chunk the upload to. Defaults to 2MB.
    """
    import boto3

    s3 = boto3.resource("s3")
    _verify_bucket(s3, s3_bucket)

    store_directory = _get_store_directory()
    minion_id = __grains__["id"]
    hostname = __grains__["host"]
    workspace = __grains__["systemlink_workspace"]
    file_name = _create_archive_file_name(hostname)
    archive_path = os.path.join(os.path.dirname(store_directory), ".archive", file_name)

    try:
        log.info(f"Creating archive {archive_path} from directory {store_directory}")
        shutil.make_archive(os.path.splitext(archive_path)[0], "zip", root_dir=store_directory)

        if destination_s3_root[-1] != "/":
            destination_s3_root += "/"
        destination_name = destination_s3_root + file_name
        full_s3_path = f"s3://{s3_bucket}/{destination_name}"
        log.info(f"Uploading {archive_path} to {full_s3_path}")
        _s3_upload_with_chunksize_and_meta(
            s3,
            archive_path,
            s3_bucket,
            destination_name,
            chunk_size_mb * MB,
            {"hostname": hostname, "systemlink-minion-id": minion_id, "systemlink-workspace": workspace},
        )
        log.info(f"Uploaded to {full_s3_path}")

        log.info(f"Cleaning store directory {store_directory}")
        _clean_directory(store_directory)
        return full_s3_path
    except Exception as ex:
        raise CommandExecutionError(f"Error while archiving to s3: {type(ex)} - {ex}")
    finally:
        try:
            log.info(f"Removing archive {archive_path}")
            os.remove(archive_path)
        except Exception:
            pass


def _s3_upload_with_chunksize_and_meta(s3, local_file_path, bucket_name, object_key, file_size_mb, metadata=None):
    """
    Upload a file from a local folder to an Amazon S3 bucket, setting a
    multipart chunk size and adding metadata to the Amazon S3 object.

    The multipart chunk size controls the size of the chunks of data that are
    sent in the request. A smaller chunk size typically results in the transfer
    manager using more threads for the upload.

    The metadata is a set of key-value pairs that are stored with the object
    in Amazon S3.

    Source:
    https://docs.aws.amazon.com/AmazonS3/latest/userguide/example_s3_Scenario_TransferManager_section.html
    """
    from boto3.s3.transfer import TransferConfig

    transfer_callback = TransferCallback(file_size_mb)

    config = TransferConfig(multipart_chunksize=file_size_mb)
    extra_args = {"Metadata": metadata} if metadata else None
    s3.Bucket(bucket_name).upload_file(
        local_file_path, object_key, Config=config, ExtraArgs=extra_args, Callback=transfer_callback
    )
    return transfer_callback.thread_info


def _verify_bucket(s3, bucket_name: str):
    try:
        s3.Bucket(bucket_name).wait_until_exists()
    except Exception as ex:
        raise ArgumentValueError("Could not access bucket " + bucket_name) from ex


def _create_archive_file_name(hostname: str) -> str:
    today = date.today().strftime("%Y%m%d")
    return f"{hostname}_store_{today}.zip"


def _get_store_directory() -> str:
    return os.path.join(_get_ni_common_appdata_dir(), "Skyline", "Data", "Store")


def _get_ni_common_appdata_dir() -> str:
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, NI_INSTALLERS_REG_PATH, 0, winreg.KEY_READ) as hkey:
        (appdata_dir, _) = winreg.QueryValueEx(hkey, NI_INSTALLERS_REG_KEY_APP_DATA)
        return appdata_dir


def _clean_directory(directory):
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)


class TransferCallback:
    """
    Handle callbacks from the transfer manager.

    The transfer manager periodically calls the __call__ method throughout
    the upload and download process so that it can take action, such as
    displaying progress to the user and collecting data about the transfer.

    Source:
    https://docs.aws.amazon.com/AmazonS3/latest/userguide/example_s3_Scenario_TransferManager_section.html
    """

    def __init__(self, target_size):
        self._target_size = target_size
        self._total_transferred = 0
        self._lock = threading.Lock()
        self.thread_info = {}

    def __call__(self, bytes_transferred):
        """
        The callback method that is called by the transfer manager.

        Display progress during file transfer and collect per-thread transfer
        data. This method can be called by multiple threads, so shared instance
        data is protected by a thread lock.
        """
        thread = threading.current_thread()
        with self._lock:
            self._total_transferred += bytes_transferred
            if thread.ident not in self.thread_info.keys():
                self.thread_info[thread.ident] = bytes_transferred
            else:
                self.thread_info[thread.ident] += bytes_transferred

            target = self._target_size * MB
            log.info(
                f"\r{self._total_transferred} of {target} transferred "
                f"({(self._total_transferred / target) * 100:.2f}%)."
            )
