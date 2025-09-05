#!/bin/bash

set -e

python -u -m third_party_license_file_generator \
    -r /srv/python-third-party-license-file-generator/requirements.txt \
    -p "$(which python)" \
    --do-not-skip-not-required-packages \
    --permit-gpl \
	--skip-prefix twine

if ! test -e THIRDPARTYLICENSES; then
    echo "error: couldn't find THIRDPARTYLICENSES- something has gone badly wrong"

    exit 1
fi

python3 /srv/python-third-party-license-file-generator/check_third_party_licenses.py
