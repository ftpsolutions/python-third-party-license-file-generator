# -*- coding: utf-8 -*-

import shutil
import os
import re
import shlex
import signal
import subprocess
import platform
from codecs import open
import sys

if sys.version_info.major >= 3:
    from dom_toml import load

from third_party_license_file_generator.licenses import (
    attempt_to_infer_license_from_license_file_name_or_file_data,
    build_license_file_for_author,
    get_license_from_github_home_page_scrape,
    get_license_from_pypi_license_scrape,
    parse_license,
)

# Metadata keys/prefixes that are created when a project is packaged using
# pyproject.toml instead of setup.py
_TOML_METADATA_HOMEPAGE_PREFIX = "Project-URL: Homepage, "
_TOML_METADATA_LICENSE_PREFIX = "Classifier: License :: OSI Approved :: "


def _pre_exec():
    signal.signal(
        signal.SIGINT, signal.SIG_IGN
    )  # to ignore CTRL+C signal in the new process


def _run_subprocess(command_line):
    if platform.system() == "Windows":
        p = subprocess.Popen(
            args=command_line.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    else:
        p = subprocess.Popen(
            args=shlex.split(command_line),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=_pre_exec,
        )

    try:
        stdout, stderr = [x.strip() for x in p.communicate()]
    except (KeyboardInterrupt, SystemExit):
        stdout, stderr = None, None

    try:
        p.terminate()
    except Exception:
        pass

    try:
        p.kill()
    except Exception:
        pass

    return (
        stdout.decode("utf-8").replace("\r\n", "\n"),
        stderr.decode("utf-8").replace("\r\n", "\n"),
        p.returncode,
    )


class Module(object):
    __slots__ = [
        "name",
        "author",
        "home_page",
        "license_name",
        "license_file",
        "requires",
    ]

    def __init__(self, name, author, home_page, license_name, license_file, requires):
        self.name = name
        self.author = author
        self.home_page = home_page
        self.license_name = license_name
        self.license_file = license_file
        self.requires = requires

    def __repr__(self):
        return "<{0}({1}) at {2}>".format(
            self.__class__.__name__,
            ", ".join(
                [
                    "{0}={1}".format(
                        x,
                        (
                            repr(getattr(self, x))[0:50] + "..."
                            if len(repr(getattr(self, x))) > 50
                            else repr(getattr(self, x))
                        ),
                    )
                    for x in self.__slots__
                ]
            ),
            hex(id(self)),
        )


_module_cache = {}


class LicenseError(Exception):
    pass


class Metadata(object):

    def __init__(self, metadata_path):
        self._metadata_path = metadata_path
        # Handy for debugging when a license isn't captured as hoped
        print("Collecting metadata for path: {}".format(metadata_path))
        self._module_name = None
        self._author = None
        self._home_page = None
        self._license_names = []
        self._requires = []
        self._top_level = []

    def set_module_name(self, module_name):
        self._module_name = module_name

    def get_module_name(self):
        return self._module_name
    def set_author(self, author):
        self._author = author

    def get_author(self):
        return self._author

    def set_home_page(self, home_page):
        self._home_page = home_page

    def get_home_page(self):
        return self._home_page

    def add_license_name(self, license_name):
        # It's common to have the license_name to be specified twice in the metadata, consider the following
        # extract:
        #
        # Metadata-Version: 2.4
        # License: ZPL-2.1
        # Keywords: interface,components,plugins
        # Classifier: License :: OSI Approved :: Zope Public License
        #
        # In previous versions of the code the last one defined would win, i.e. Zope Public License in this case
        # However, we can see that information is lost. It's assumed that the later definition under the
        # Classifier section may sometimes be more accurate. Thus we keep track of all license name references
        # so they are all available later when do license analysis
        print("Adding license name: {} from metadata: {}".format(license_name, self._metadata_path))
        self._license_names.append(license_name)

    def get_license_names(self):
        return self._license_names

    def add_requires(self, require_entry):
        self._requires.append(require_entry)

    def get_requires(self):
        return self._requires

    def set_top_level(self, top_level):
        # top_level is not found in the metadata file,
        # but declaring along with the metadata so the lifetime is linked to this object
        self._top_level = top_level

    def get_top_level(self):
        return self._top_level

    def _set_metadata_dict_value(self, key, value):
        # In the implementation of the metadata parsing we look for keys that are present in
        # older style setup.py metadata AND newer style pyproject.toml metadata.
        # We don't expect to encounter a situation where this presents an issue, but it might.
        # Add some logging for this case.
        current_value = getattr(self, key, None)
        if current_value is not None:
            print(
                "\nINFO: For METADATA {}\n\tkey {} is already set in parsed metadata. Changing value from {} to {}".format(
                    repr(self._metadata_path),
                    repr(key),
                    repr(current_value),
                    repr(value),
                )
            )
        setattr(self, key, value)


class SitePackages(object):
    def __init__(
        self,
        requirements_path,
        python_path=None,
        skip_prefixes=None,
        autorun=True,
        use_internet=True,
        license_overrides=None,
        do_not_skip_not_required_packages=False,
    ):
        self._requirements_path = requirements_path
        self._python_path = (
            python_path if python_path is not None else shutil.which("python3")
        )  # noqa
        self._skip_prefixes = skip_prefixes
        self._use_internet = use_internet
        self._license_overrides = (
            license_overrides if license_overrides is not None else {}
        )
        self._do_not_skip_not_required_packages = do_not_skip_not_required_packages

        self._root_module_names = set()
        self._required_module_names = set()
        self._module_metadatas_by_module_name = {}
        self._module_licenses_by_module_name = {}
        self._modules_by_module_name = {}
        self._stub_licenses = {}

        if not autorun:
            return

        self.run()

    @property
    def modules_by_module_name(self):
        return self._modules_by_module_name

    @property
    def modules_by_license_name(self):
        modules_by_license_name = {}

        for _, module in sorted(self._modules_by_module_name.items()):
            modules_by_license_name.setdefault(module.license_name, [])
            modules_by_license_name[module.license_name] += [module]

        return modules_by_license_name

    def _read_pyproject_toml(self, requirements_path):
        data = load(requirements_path)

        deps = data.get("project", {}).get("dependencies")
        if deps is None:
            print("No dependencies found in {}".format(repr(requirements_path)))
        else:
            for line in deps:
                matches = [x for x in re.finditer(r"(^[\w|-|_]+).*$", line)]

                for match in matches:
                    if not match:
                        continue

                    for group in match.groups():
                        self._root_module_names.add(group)

    def _read_requirements(self, requirements_path):
        with open(requirements_path, "r") as f:
            data = f.read()

        for raw_line in data.split("\n"):
            line = ""
            for c in raw_line:
                if c == "#":
                    break

                line += c

            line = line.strip()
            if line == "":
                continue

            if line.startswith("-r "):
                self._read_requirements(
                    os.path.join(
                        os.path.split(requirements_path)[0],
                        "-r ".join(line.split("-r ")[1:]).strip(),
                    )
                )
            elif "--" in line:
                continue
            else:
                matches = [x for x in re.finditer(r"(^[\w|-|_]+).*$", line)]

                for match in matches:
                    if not match:
                        continue

                    for group in match.groups():
                        self._root_module_names.add(group)

    def _get_site_packages_folder(self):
        out, err, returncode = _run_subprocess("{0} -m site".format(self._python_path))

        try:
            sys_path = eval(out.split("sys.path =")[-1].split("]")[0] + "]")
        except Exception:
            return None

        try:
            # typically we should see this
            site_packages_path = [x for x in sys_path if "site-packages" in x][0]
        except Exception:
            try:
                # though it seems that Ubuntu containers may see this
                site_packages_path = [x for x in sys_path if "dist-packages" in x][0]
            except Exception:
                return None

        return site_packages_path

    def _read_metadata(self, metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = f.read().replace("\r\n", "\n")

        interesting_data = data.split("\n\n")[0].strip()

        metadata = Metadata(metadata_path=metadata_path)

        for line in [
            x.strip() for x in interesting_data.split("\n") if x.strip() != ""
        ]:
            parts = line.split(": ")
            key = parts[0].strip()
            value = ": ".join(parts[1:]).strip()

            if key == "Name":
                metadata.set_module_name(value)
            elif key == "Author":
                metadata.set_author(value)
            elif key == "Author-email":
                if metadata.get_author() is None:
                    metadata.set_author("(unknown)")

                author = metadata.get_author()
                author += " <{0}>".format(value)
                metadata.set_author(author.strip())
            elif key == "Home-page":
                # Used for setup.py metadata packages
                metadata.set_home_page(value)
            elif key == "License":
                # Used for setup.py metadata packages
                metadata.add_license_name(value)
            elif key == "License-Expression":
                # Used for setup.py metadata packages
                # Some packages prefer this over the License key
                metadata.add_license_name(value)
            elif line.startswith(_TOML_METADATA_HOMEPAGE_PREFIX):
                # Used for pyproject.toml metadata packages
                # Line example: Project-URL: Homepage, https://github.com/carltongibson/django-filter/tree/main
                metadata.set_home_page(line.split(_TOML_METADATA_HOMEPAGE_PREFIX)[-1])
            elif line.startswith(_TOML_METADATA_LICENSE_PREFIX):
                # Used for pyproject.toml metadata packages
                # Line example:
                # Classifier: License :: OSI Approved :: MIT License
                metadata.add_license_name(line.split(_TOML_METADATA_LICENSE_PREFIX)[-1])
            elif key == "Requires-Dist":
                if ";" not in value:
                    module_name = (
                        value.split("(")[0]
                        .split("<")[0]
                        .split(">")[0]
                        .split("=")[0]
                        .strip()
                    )
                    if module_name != "":
                        metadata.add_requires(module_name)

        return metadata

    @staticmethod
    def _read_top_level(top_level_path):
        with open(top_level_path, "r") as f:
            data = f.read()
        return [x for x in data.split("\n") if x]

    def _read_all_module_metadatas_and_license_files(self):
        site_packages_path = self._get_site_packages_folder()

        for thing in os.listdir(site_packages_path):
            path_to_thing = os.path.join(site_packages_path, thing)
            if not os.path.isdir(path_to_thing):
                continue

            if not thing.endswith("dist-info"):
                if thing.endswith(".egg") and os.path.isdir(
                    os.path.join(path_to_thing, "EGG-INFO")
                ):
                    path_to_thing = os.path.join(path_to_thing, "EGG-INFO")
                else:
                    continue

            metadata = None
            metadata_path = None
            license_file = None
            license_file_path = None
            top_level = None

            for sub_thing in os.listdir(path_to_thing):
                path_to_sub_thing = os.path.join(path_to_thing, sub_thing)
                if not os.path.isfile(path_to_sub_thing):
                    continue

                if sub_thing == "METADATA" or sub_thing == "PKG-INFO":
                    if metadata is None:
                        metadata = self._read_metadata(path_to_sub_thing)
                        metadata_path = path_to_sub_thing
                elif (
                    "LICENSE" in sub_thing
                    or "COPYING" in sub_thing
                    or "LICENCE" in sub_thing
                ):
                    if license_file is None:
                        possible_license_file = self._read_license(path_to_sub_thing)
                        possible_license_name = attempt_to_infer_license_from_license_file_name_or_file_data(
                            path_to_sub_thing, possible_license_file
                        )
                        if (
                            possible_license_name
                            and possible_license_name != "Commercial"
                        ):
                            license_file = possible_license_file
                            license_file_path = path_to_sub_thing
                elif sub_thing == "top_level.txt":
                    # Some packages include this file - it's useful when the top level import is different
                    # to the package name, e.g. mysql_connector offers mysql as a top level import.
                    # Newline separated list of top level imported packages
                    top_level = self._read_top_level(path_to_sub_thing)

            if license_file is None:
                licences_folder_path_a = os.path.join(path_to_thing, "licenses")
                licences_folder_path_b = os.path.join(path_to_thing, "licences")

                possible_licence_file_paths = []

                for licences_folder_path in [
                    licences_folder_path_a,
                    licences_folder_path_b,
                ]:
                    if os.path.exists(licences_folder_path) and os.path.isdir(
                        licences_folder_path
                    ):
                        for sub_thing in os.listdir(licences_folder_path):
                            path_to_sub_thing = os.path.join(
                                licences_folder_path, sub_thing
                            )

                            if not os.path.isfile(path_to_sub_thing):
                                continue

                            if (
                                "LICENSE" in sub_thing
                                or "COPYING" in sub_thing
                                or "LICENCE" in sub_thing
                            ):
                                possible_licence_file_paths.append(path_to_sub_thing)

                if license_file is None:
                    for possible_licence_file_path in possible_licence_file_paths:
                        possible_license_file = self._read_license(
                            possible_licence_file_path
                        )
                        possible_license_name = attempt_to_infer_license_from_license_file_name_or_file_data(
                            possible_licence_file_path, possible_license_file
                        )
                        if (
                            possible_license_name is not None
                            and possible_license_name != "Commercial"
                        ):
                            license_file = possible_license_file
                            license_file_path = possible_licence_file_path
                            break

            if metadata is None:
                continue

            module_name = metadata.get_module_name()

            if top_level is not None:
                if module_name not in top_level:
                    print("INFO: {} has imports not overlapping with the module name {}".format(module_name, top_level))
                metadata.set_top_level(top_level)

            if not metadata.get_license_names():
                possible_license_name = (
                    attempt_to_infer_license_from_license_file_name_or_file_data(
                        license_file_path, license_file
                    )
                )
                if possible_license_name:
                    print(
                        "\nINFO: For METADATA {}\n\tkey {} was empty / unset. Changing value from {} to {} (inferred by reading {})".format(
                            repr(metadata_path),
                            repr("license_name"),
                            repr(metadata.get_license_names()),
                            repr(possible_license_name),
                            repr(license_file_path),
                        )
                    )

                    metadata.add_license_name(possible_license_name)

            if (
                module_name in self._root_module_names
                or module_name in self._required_module_names
            ):
                for required_module_name in metadata.get_requires():
                    self._required_module_names.add(required_module_name)

            self._module_metadatas_by_module_name[module_name] = metadata

            if license_file is not None:
                self._module_licenses_by_module_name[module_name] = license_file

    def _read_license(self, license_path):
        with open(license_path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()

        return data.strip()

    def _read_site_packages(self):
        for module_name, metadata in self._module_metadatas_by_module_name.items():
            # Account for the fact that the provided top level imports may not match the module name
            possible_module_names = [module_name] + metadata.get_top_level()
            if (
                not self._do_not_skip_not_required_packages
                and all([name not in self._root_module_names for name in possible_module_names])
                and all([name not in self._required_module_names for name in possible_module_names])
            ):
                continue

            if self._skip_prefixes is not None:
                if any([module_name.startswith(x) for x in self._skip_prefixes]):
                    continue

            if module_name in self._modules_by_module_name:
                continue

            if module_name in _module_cache:
                module = _module_cache[module_name]
                self._modules_by_module_name[module_name] = module
                continue

            author = metadata.get_author()
            home_page = metadata.get_home_page()

            overridden_license_name = None
            overridden_license_file = None

            license_override = self._license_overrides.get(module_name)
            if license_override:
                overridden_license_name = license_override.get("license_name")
                overridden_license_file = license_override.get("license_file")

            if None not in [overridden_license_name, overridden_license_file]:
                license_name = overridden_license_name
                license_file = overridden_license_file
            else:
                original_license_name = None
                license_name = None

                for ln in metadata.get_license_names():
                    # Iterate through the licenses until we find a non null result.
                    # parse_license() _mostly_ looks for a specific format, i.e. LIC-X,
                    # e.g. GPL-3.0, ZPL-2.1
                    # It's possible in the metadata license names to have variations like
                    # "Zope Public License" which misses all of the checks, plus it's missing
                    # license version info. It's been observed, in these cases there will
                    # be a second entry matching the format that we expect - so we prefer that.
                    # No doubt more edge cases will arise later since there are no guarantees on
                    # what goes into a package's metadata - applying YAGNI
                    original_license_name = ln
                    license_name = parse_license(ln)
                    if license_name is not None:
                        break

                # Note in the event of failure to match, the last original_license_name wins
                # This matches legacy behaviour

                license_file = self._module_licenses_by_module_name.get(module_name)

                github_license_file = None
                if original_license_name not in ["Commercial"]:
                    if license_name is None and self._use_internet:
                        pypi_license_name = get_license_from_pypi_license_scrape(
                            module_name
                        )
                        license_name = parse_license(pypi_license_name)

                        if license_name is None:
                            if (
                                home_page is not None
                                and "github" in home_page
                                and self._use_internet
                            ):
                                github_license_file = (
                                    get_license_from_github_home_page_scrape(home_page)
                                )
                                license_name = parse_license(github_license_file)

                                if license_file is None:
                                    license_file = github_license_file

                if license_file is None:
                    if (
                        home_page is not None
                        and github_license_file is None
                        and self._use_internet
                    ):
                        github_license_file = get_license_from_github_home_page_scrape(
                            home_page
                        )

                    license_file = github_license_file

                if license_file is None and license_name is not None:
                    license_file = build_license_file_for_author(author, license_name)

                if license_name is None:
                    license_name = "Unknown (assumed commercial)"
                    license_file = build_license_file_for_author(author, "Commercial")

            module = Module(
                name=module_name,
                author=metadata.get_author(),
                home_page=metadata.get_home_page(),
                license_name=license_name,
                license_file=license_file,
                requires=metadata.get_requires(),
            )

            self._modules_by_module_name[module_name] = module

            if module_name not in _module_cache:
                _module_cache[module_name] = module

    def run(self):
        if self._requirements_path.endswith(".toml"):
            if load is not None:
                self._read_pyproject_toml(self._requirements_path)
            else:
                raise ValueError("TOML not supported for Python 2")
        else:
            self._read_requirements(self._requirements_path)

        while True:
            last_root_module_names = self._root_module_names.copy()
            last_required_module_names = self._required_module_names.copy()

            self._read_all_module_metadatas_and_license_files()

            if (
                last_root_module_names == self._root_module_names
                and last_required_module_names == self._required_module_names
            ):
                break

        self._read_site_packages()

    def __add__(self, other):
        if not isinstance(other, self.__class__):
            raise TypeError(
                "cannot add {0} and {1}".format(self.__class__, other.__class__)
            )

        result = SitePackages(
            requirements_path=None,
            python_path=None,
            autorun=False,
        )

        result._modules_by_module_name = self._modules_by_module_name

        for module_name, module in other._modules_by_module_name.items():
            result._modules_by_module_name[module_name] = module

        return result

    def __sub__(self, other):
        if not isinstance(other, self.__class__):
            raise TypeError(
                "cannot subtract {0} and {1}".format(self.__class__, other.__class__)
            )

        result = SitePackages(
            requirements_path=None,
            python_path=None,
            autorun=False,
        )

        result._modules_by_module_name = self._modules_by_module_name

        for module_name, module in other._modules_by_module_name.items():
            result._modules_by_module_name.pop(module_name, None)

        return result
