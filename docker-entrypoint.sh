#!/bin/bash

set -e

# Test parse and generation of THIRDPARTYLICENSES from requirements.txt
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

python3 -u /srv/python-third-party-license-file-generator/check_third_party_licenses.py

rm THIRDPARTYLICENSES

# Test parse and generation of THIRDPARTYLICENSES from pyproject.toml (if Python version is 3.x)
if python -c "import sys; sys.exit(0 if sys.version_info.major >= 3 else 1)" 2>/dev/null
then
    python -u -m third_party_license_file_generator \
    -r /srv/python-third-party-license-file-generator/pyproject.toml \
    -p "$(which python)" \
    --do-not-skip-not-required-packages \
    --permit-gpl \
	--skip-prefix twine

    if ! test -e THIRDPARTYLICENSES; then
        echo "error: couldn't find THIRDPARTYLICENSES- something has gone badly wrong"

        exit 1
    fi

    python3 -u /srv/python-third-party-license-file-generator/check_third_party_licenses.py
fi
