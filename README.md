# systemlink-store-archiver

SystemLink Store Archiver is a SaltStack module for achiving SystemLink 
Store and Forward's store directory to allow moving it to another machine
for processing in cases where problems have caused a signifacnt backlog of
forwarding requests to process. 

The execution module supports uploading the archive to both the SystemLink File 
service, and directly to a AWS S3 bucket. Be aware that the SystemLink File service
has a 200MB download limit, so if you expect the archive to be larger than that,
consider using S3 instead.

For more information on SaltStack see [Salt States](https://docs.saltstack.com/en/latest/topics/tutorials/starting_states.html) 
and [Salt Execution Modules](https://docs.saltproject.io/en/latest/ref/modules/index.html#writing-execution-modules).

## Installation and configuration

1. Copy the `src/systemlink_store_archiver.py` to your server's salt root
   - Defaults to `C:\ProgramData\National Instruments\salt\srv\salt`
2. Import `salt\archive_store_to_file_service.sls` or `salt\archive_store_to_s3.sls` as a new state in the SystemLink States web UI
   - Open **System Management** > **States** from the navigation menu
   - Click the **Import** button in the toolbar
   - Browse to the .sls file
3. If uploading to S3, update the placeholder values in `<>` in the .sls file with values for your S3 bucket
   - The credentials used for the operation requires write access to the bucket (`s3:PutObject` action).
   See [AWS documentation](https://docs.aws.amazon.com/sdkref/latest/guide/creds-config-files.html) for 
   how to provide credentials. The environment variables used in the .sls file are just one way of providing credentials.
   - If putting the credentials in the .sls file, we recommend creating a new IAM user with limited privileges
   and revoking the access token when you're done. See the [AWS S3: Read and write acces to objects in an S3 Bucket](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_examples_s3_rw-bucket.html) 
   example for details on how to setup the bucket permissions.
4. [Apply the state](https://www.ni.com/documentation/en/systemlink/latest/deployment/deploying-system-states/) 
   to the systems you'd like to archive

## Development

`systemlink-store-archiver` uses [poetry](https://python-poetry.org/) 
to manage dependencies and Python version 3.6.8, which matches the version of
Python included on SystemLink Client 2021 R1 through 2022 Q1 installations.