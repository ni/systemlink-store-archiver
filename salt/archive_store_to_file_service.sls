'C:\ProgramData\National Instruments\salt\var\extmods\modules\systemlink_store_archiver.py':
  file.managed:
    - source: salt://systemlink_store_archiver.py

saltutil.refresh_modules:
  module.run:
    - async: False

service.stop:
  module.run:
    - m_name: nisystemlinkforwarding

systemlink_store_archiver.archive_to_file_service:
  module.run

service.start:
  module.run:
    - m_name: nisystemlinkforwarding
