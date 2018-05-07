# -*- coding: utf-8 -*-

import distutils
import os
import shlex
import signal
import subprocess

from third_party_license_file_generator.licenses import (build_license_file_for_author,
                                                         get_license_from_github_home_page_scrape,
                                                         get_license_from_pypi_license_scrape,
                                                         parse_license)


def _pre_exec():
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # to ignore CTRL+C signal in the new process


def _run_subprocess(command_line):
    p = subprocess.Popen(
        shlex.split(command_line),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=_pre_exec
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
        stdout.decode('utf-8').replace('\r\n', '\n'),
        stderr.decode('utf-8').replace('\r\n', '\n'),
        p.returncode
    )


class Module(object):
    __slots__ = ['name', 'author', 'home_page', 'license_name', 'license_file', 'requires']

    def __init__(self, name, author, home_page, license_name, license_file, requires):
        self.name = name
        self.author = author
        self.home_page = home_page
        self.license_name = license_name
        self.license_file = license_file
        self.requires = requires

    def __repr__(self):
        return '<{0}({1}) at {2}>'.format(
            self.__class__.__name__,
            ', '.join([
                '{0}={1}'.format(
                    x,
                    repr(getattr(self, x))[0:50] + '...' if len(repr(getattr(self, x))) > 50 else repr(getattr(self, x))
                ) for x in self.__slots__
            ]),
            hex(id(self))
        )


_module_cache = {}


class LicenseError(Exception):
    pass


class SitePackages(object):
    def __init__(self, requirements_path, python_path=None, skip_prefixes=None,
                 autorun=True, use_internet=True, license_overrides=None):
        self._requirements_path = requirements_path
        self._python_path = python_path if python_path is not None else distutils.spawn.find_executable('python3')
        self._skip_prefixes = skip_prefixes
        self._use_internet = use_internet
        self._license_overrides = license_overrides if license_overrides is not None else {}

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

    def _read_requirements(self, requirements_path):
        with open(requirements_path, 'r') as f:
            data = f.read()

        for raw_line in data.split('\n'):
            line = ''
            for c in raw_line:
                if c == '#':
                    break

                line += c

            line = line.strip()
            if line == '':
                continue

            if line.startswith('-r '):
                self._read_requirements(
                    os.path.join(
                        os.path.split(requirements_path)[0],
                        '-r '.join(line.split('-r ')[1:]).strip()
                    )

                )
            elif '--' in line:
                continue
            else:
                self._root_module_names.add(line.split('==')[0].strip())

    def _get_site_packages_folder(self):
        out, err, returncode = _run_subprocess('{0} -m site'.format(
            self._python_path
        ))

        try:
            sys_path = eval(
                out.split('sys.path =')[-1].split(']')[0] + ']'
            )
        except Exception:
            return None

        try:
            site_packages_path = [
                x for x in sys_path if '/site-packages' in x
            ][0]
        except Exception:
            return None

        return site_packages_path

    def _read_metadata(self, metadata_path):
        with open(metadata_path, 'r') as f:
            data = f.read().replace('\r\n', '\n')

        interesting_data = data.split('\n\n')[0].strip()

        metadata = {
            'module_name': None,
            'author': None,
            'home_page': None,
            'license_name': None,
            'requires': [],
        }

        for line in [x.strip() for x in interesting_data.split('\n') if x.strip() != '']:
            parts = line.split(': ')
            key = parts[0].strip()
            value = ': '.join(parts[1:]).strip()

            if key == 'Name':
                metadata['module_name'] = value
            elif key == 'Author':
                metadata['author'] = value
            elif key == 'Author-email':
                if metadata['author'] is None:
                    metadata['author'] = '(unknown)'

                metadata['author'] += ' <{0}>'.format(value)
                metadata['author'] = metadata['author'].strip()
            elif key == 'Home-page':
                metadata['home_page'] = value
            elif key == 'License':
                metadata['license_name'] = value
            elif key == 'Requires-Dist':
                if ';' not in value:
                    module_name = value.split('(')[0].split('<')[0].split('>')[0].split('=')[0].strip()
                    if module_name != '':
                        metadata['requires'] += [module_name]

        return metadata

    def _read_all_module_metadatas_and_license_files(self):
        site_packages_path = self._get_site_packages_folder()

        for thing in os.listdir(site_packages_path):
            path_to_thing = os.path.join(site_packages_path, thing)
            if not os.path.isdir(path_to_thing):
                continue

            if not thing.endswith('dist-info'):
                continue

            metadata = None
            license_file = None
            for sub_thing in os.listdir(path_to_thing):
                path_to_sub_thing = '{0}/{1}'.format(path_to_thing, sub_thing)
                if not os.path.isfile(path_to_sub_thing):
                    continue

                if sub_thing == 'METADATA':
                    metadata = self._read_metadata(path_to_sub_thing)
                elif 'LICENSE' in sub_thing:
                    license_file = self._read_license(path_to_sub_thing)

            if metadata is None:
                continue

            module_name = metadata['module_name']

            if module_name in self._root_module_names or module_name in self._required_module_names:
                for required_module_name in metadata['requires']:
                    self._required_module_names.add(required_module_name)

            self._module_metadatas_by_module_name[module_name] = metadata

            if license_file is not None:
                self._module_licenses_by_module_name[module_name] = license_file

    def _read_license(self, license_path):
        with open(license_path, 'r') as f:
            data = f.read()

        return data.strip()

    def _read_site_packages(self):
        for module_name, metadata in self._module_metadatas_by_module_name.items():
            if module_name not in self._root_module_names and module_name not in self._required_module_names:
                # print('skipping', module_name, 'as it\'s not in the root modules or any of their requirements')
                # print('')
                continue

            if self._skip_prefixes is not None:
                if any([module_name.startswith(x) for x in self._skip_prefixes]):
                    # print('skipping', module_name, 'as it meets one of the specified skip prefixes')
                    # print('')
                    continue

            if module_name in self._modules_by_module_name:
                continue

            # print('handling', repr(module_name))

            if module_name in _module_cache:
                module = _module_cache[module_name]
                self._modules_by_module_name[module_name] = module
                # print('using cached', module)
                # print('')
                continue

            author = metadata['author']
            home_page = metadata['home_page']

            overriden_license_name = None
            overriden_license_file = None

            license_override = self._license_overrides.get(module_name)
            if module_name in self._license_overrides:
                overriden_license_name = license_override.get('license_name')
                overriden_license_file = license_override.get('license_file')

            if None not in [overriden_license_name, overriden_license_file]:
                license_name = overriden_license_name
                license_file = overriden_license_file
            else:
                original_license_name = metadata['license_name']
                license_file = self._module_licenses_by_module_name.get(module_name)

                # print('details are', [author, home_page, original_license_name])

                license_name = parse_license(original_license_name)
                # if license_name is not None:
                #     print('got license_name', repr(license_name))

                # if license_file is not None:
                #     print('got license_file from module folder')

                github_license_file = None
                if original_license_name not in ['Commercial']:
                    if license_name is None and self._use_internet:
                        pypi_license_name = get_license_from_pypi_license_scrape(module_name)
                        license_name = parse_license(pypi_license_name)
                        # if license_name is not None:
                        #     print('got license_name from PyPI', repr(license_name))

                        if license_name is None:
                            if home_page is not None and 'github' in home_page and self._use_internet:
                                github_license_file = get_license_from_github_home_page_scrape(home_page)
                                license_name = parse_license(github_license_file)
                                # if license_name is not None:
                                #     print('got license_name from Github repo', repr(license_name))

                                if license_file is None:
                                    license_file = github_license_file

                                    # if license_file is not None:
                                    #     print('got license_file from Github repo')

                if license_file is None:
                    if github_license_file is None and self._use_internet:
                        github_license_file = get_license_from_github_home_page_scrape(home_page)

                    license_file = github_license_file
                    # if license_file is not None:
                    #     print('got license_file from Github repo')

                if license_file is None and license_name is not None:
                    license_file = build_license_file_for_author(author, license_name)
                    # if license_file is not None:
                    #     print('built license_file from local store')

                # if license_name is None:
                #     print('warning: all attempts to get license_name failed')
                # elif license_file is None:
                #     print('warning: all attempts to get license_file failed')

                if license_name is None:
                    license_name = 'Unknown (assumed commercial)'
                    license_file = build_license_file_for_author(author, 'Commercial')

            module = Module(
                name=module_name,
                author=metadata['author'],
                home_page=metadata['home_page'],
                license_name=license_name,
                license_file=license_file,
                requires=metadata['requires']
            )

            # print('built', module)
            # print('')

            self._modules_by_module_name[module_name] = module

            if module_name not in _module_cache:
                _module_cache[module_name] = module

    def run(self):
        self._read_requirements(self._requirements_path)

        while True:
            last_root_module_names = self._root_module_names.copy()
            last_required_module_names = self._required_module_names.copy()

            self._read_all_module_metadatas_and_license_files()

            if last_root_module_names == self._root_module_names and last_required_module_names == self._required_module_names:
                break

        self._read_site_packages()

    def __add__(self, other):
        if not isinstance(other, self.__class__):
            raise TypeError('cannot add {0} and {1}'.format(
                self.__class__, other.__class__
            ))

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
            raise TypeError('cannot subtract {0} and {1}'.format(
                self.__class__, other.__class__
            ))

        result = SitePackages(
            requirements_path=None,
            python_path=None,
            autorun=False,
        )

        result._modules_by_module_name = self._modules_by_module_name

        for module_name, module in other._modules_by_module_name.items():
            result._modules_by_module_name.pop(module_name, None)

        return result
