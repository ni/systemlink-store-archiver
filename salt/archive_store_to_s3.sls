Setup-AWS-Env:
  - environ.setenv:
    - value:
        AWS_ACCESS_KEY_ID: <foo>
        AWS_SECRET_ACCESS_KEY: <bar>
        AWS_DEFAULT_REGION: <baz>

boto3:
  pip.installed:
    - name: boto3 >= 1.15, < 1.16

'C:\ProgramData\National Instruments\salt\var\extmods\modules\systemlink_store_archiver.py':
  file.managed:
    - source: salt://systemlink_store_archiver.py

saltutil.refresh_modules:
  module.run:
    - async: False

service.stop:
  module.run:
    - m_name: nisystemlinkforwarding

systemlink_store_archiver.archive_to_s3:
  module.run:
    - s3_bucket: <bucket>
    - destination_s3_root: <desired_object_root>

service.start:
  module.run:
    - m_name: nisystemlinkforwarding
