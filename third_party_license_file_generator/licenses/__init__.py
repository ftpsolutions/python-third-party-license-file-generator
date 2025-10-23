# -*- coding: utf-8 -*-

import re
import requests
import datetime

from third_party_license_file_generator.licenses.apache_1_1 import data as apache_1_1
from third_party_license_file_generator.licenses.apache_2_0 import data as apache_2_0
from third_party_license_file_generator.licenses.bsd_2_clause import (
    data as bsd_2_clause,
)
from third_party_license_file_generator.licenses.bsd_3_clause import (
    data as bsd_3_clause,
)
from third_party_license_file_generator.licenses.gpl_2_0 import data as gpl_2_0
from third_party_license_file_generator.licenses.gpl_3_0 import data as gpl_3_0
from third_party_license_file_generator.licenses.isc import data as isc
from third_party_license_file_generator.licenses.lgpl_2_1 import data as lgpl_2_1
from third_party_license_file_generator.licenses.lgpl_3_0 import data as lgpl_3_0
from third_party_license_file_generator.licenses.mit import data as mit
from third_party_license_file_generator.licenses.mpl_1_0 import data as mpl_1_0
from third_party_license_file_generator.licenses.mpl_1_1 import data as mpl_1_1
from third_party_license_file_generator.licenses.mpl_2_0 import data as mpl_2_0
from third_party_license_file_generator.licenses.pil import data as pil
from third_party_license_file_generator.licenses.python_2_0 import data as python_2_0

license_files = {
    "apache-1.1": apache_1_1,
    "apache-2.0": apache_2_0,
    "bsd-2-clause": bsd_2_clause,
    "bsd-3-clause": bsd_3_clause,
    "commercial": "This package is under a commercial license; be extremely careful.",
    "gpl-2.0": gpl_2_0,
    "gpl-3.0": gpl_3_0,
    "isc": isc,
    "lgpl-2.1": lgpl_2_1,
    "lgpl-3.0": lgpl_3_0,
    "mit": mit,
    "mpl-1.0": mpl_1_0,
    "mpl-1.1": mpl_1_1,
    "mpl-2.0": mpl_2_0,
    "pil": pil,
    "python-2.0": python_2_0,
}

license_friendly = {
    "apache-1.1": "Apache-1.1",
    "apache-2.0": "Apache-2.0",
    "bsd-2-clause": "BSD-2-clause",
    "bsd-3-clause": "BSD-3-clause",
    "commercial": "Commercial",
    "gpl-2.0": "GPL-2.0",
    "gpl-3.0": "GPL-3.0",
    "isc": "ISC",
    "lgpl-2.1": "LGPL-2.1",
    "lgpl-3.0": "LGPL-3.0",
    "mit": "MIT",
    "mpl-1.0": "MPL-1.0",
    "mpl-1.1": "MPL-1.1",
    "mpl-2.0": "MPL-2.0",
    "pil": "PIL",
    "python-2.0": "Python-2.0",
}

assert set(license_friendly.keys()) == set(license_files.keys())

_MIT_BLURB = """Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions"""

text_to_license = {
    "Apache Software License": "apache-1.1",
    "Apache License Version 2.0": "apache-2.0",
    "2-Clause BSD License": "bsd-2-clause",
    "New BSD License": "bsd-3-clause",
    "Modified BSD License": "bsd-3-clause",
    "BSD 3-Clause License": "bsd-3-clause",
    "__COMMERCIAL_MAGIC_TOKEN_COMMERCIAL__": "commercial",
    "GNU GENERAL PUBLIC LICENSE Version 2": "gpl-2.0",
    "GNU GENERAL PUBLIC LICENSE Version 3": "gpl-3.0",
    "ISC License": "isc",
    "GNU Lesser General Public License Version 2.1": "lgpl-2.1",
    "GNU LESSER GENERAL PUBLIC LICENSE Version 3": "lgpl-3.0",
    "MIT License": "mit",
    "MIT No Attribution": "mit",
    _MIT_BLURB: "mit",
    "Mozilla Public License Version 1.0": "mpl-1.0",
    "Mozilla Public License 1.1": "mpl-1.1",
    "Mozilla Public License version 2.0": "mpl-2.0",
    "Python Imaging Library": "pil",
    "Python License Version 2": "python-2.0",
    "PSF License Version 2": "python-2.0",
}

assert set(text_to_license.values()) == set(license_files.keys())


def _safe_check(source, match):
    if re.match("[A-UW-Za-uw-z]{0}".format(match), source) is not None:
        return False

    if re.match("{0}[A-UW-Za-uw-z]".format(match), source) is not None:
        return False

    if match in source:
        return True

    return False


def parse_license(raw_license):
    if raw_license in [None, "UNKNOWN"]:
        return None

    compare_license = re.sub("[1-2][0-9][0-9][0-9]", "", raw_license)

    if _safe_check(compare_license, "LGPL"):
        if "2" in compare_license:
            return "LGPL-2.1"
        else:
            return "LGPL-3.0"
    elif _safe_check(compare_license, "GPL"):
        if "2" in compare_license:
            return "GPL-2.0"
        else:
            return "GPL-3.0"
    elif _safe_check(compare_license, "Apache") or _safe_check(compare_license, "ASL"):
        if "1" in compare_license:
            return "Apache-1.1"
        else:
            return "Apache-2.0"
    elif _safe_check(compare_license, "BSD"):
        if "2" in compare_license or "Simpl" in compare_license:
            return "BSD-2-clause"
        else:
            return "BSD-3-clause"
    elif _safe_check(compare_license, "PSF") or _safe_check(compare_license, "Python"):
        return "Python-2.0"
    elif _safe_check(compare_license, "MIT") or _safe_check(compare_license, "Expat"):
        return "MIT"
    elif _safe_check(compare_license, "MPL") or _safe_check(compare_license, "Mozilla"):
        if compare_license.count("1") == 1:
            return "MPL-1.0"
        elif compare_license.count("1") == 2:
            return "MPL-1.1"
        else:
            return "MPL-2.0"
    elif _safe_check(compare_license, "ISC"):
        return "ISC"
    elif _safe_check(compare_license, "PIL"):
        return "PIL"
    elif _safe_check(compare_license, "Commercial"):
        return "Commercial"
    elif _safe_check(compare_license, "Unknown (assumed commercial)"):
        return "Unknown (assumed commercial)"

    return None


def get_license_from_pypi_license_scrape(module_name):
    try:
        r = requests.get("https://pypi.org/project/{0}".format(module_name), timeout=5)
    except Exception:
        return None

    if r.status_code != 200:
        return None

    match = re.search("License:</.+>([^<]+)", r.text)
    return match.group(1).strip() if match is not None else None


def get_license_from_github_home_page_scrape(url):
    repo = url.split("github.com/repos/")[-1].split("github.com/")[-1]

    possible_licenses = [
        "LICENSE",
        "LICENSE.txt",
        "LICENSE.md",
        "LICENCE",
        "LICENCE.txt",
        "LICENCE.md",
    ]

    license_file = None
    for possible_license in possible_licenses:
        possible_license_url = (
            "https://raw.githubusercontent.com/{0}/master/{1}".format(
                repo, possible_license
            )
        )

        try:
            r = requests.get(possible_license_url, timeout=5)
        except Exception as e:
            return None

        if r.status_code != 200:
            continue

        license_file = r.text

    return license_file


def build_license_file_for_author(author, license_name):
    license_file = license_files.get(license_name.lower())
    if license_file is None:
        return None

    license_file = license_file.replace("<YEAR>", str(datetime.datetime.now().year))
    license_file = license_file.replace(
        "<COPYRIGHT HOLDER>", author if author is not None else "(author unknown)"
    )
    license_file = license_file.replace(
        "<OWNER>", author if author is not None else "(author author)"
    )

    return "NOTE: This module was missing a license file (despite listing a license name) so one has been auto-generated\n\n{0}".format(
        license_file.strip()
    )


def attempt_to_infer_license_from_license_file_name_or_file_data(
    license_file_name, license_file_data
):
    if not license_file_name and not license_file_data:
        return None

    # first try for a file name match
    if isinstance(license_file_name, str):
        for licence_name in license_files.keys():
            if licence_name == "commercial":
                continue

            if license_file_name.endswith(licence_name):
                return license_friendly[licence_name]

    # otherwise see if the licence is mentioned in the file
    if isinstance(license_file_data, str):
        license_file_data_1 = " ".join(license_file_data.split())
        license_file_data_2 = license_file_data_1.replace(",", " ")

        for text, licence_name in text_to_license.items():
            if licence_name == "commercial":
                continue

            if (
                text.upper() in license_file_data_1.upper()
                or text.upper() in license_file_data_2.upper()
            ):
                return license_friendly[licence_name]

        for licence_name, licence_name_friendly in license_friendly.items():
            if licence_name == "commercial":
                continue

            if " " + licence_name_friendly + " " in license_file_data:
                return licence_name_friendly
