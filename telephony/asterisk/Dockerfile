# Asterisk 23 with Tellerline's configuration built in (docs/PHONE.md).
#
# The configuration is copied in rather than mounted: macOS keeps a VM's file sharing out of
# Desktop and Documents, where the repository may well live. It goes in its own directory, read
# with `asterisk -C` (compose.yaml), because the image's /etc/asterisk is a volume full of sample
# configuration that a build can't remove.
FROM andrius/asterisk:23.4.1_debian-forky
COPY etc/ /etc/tellerline/
