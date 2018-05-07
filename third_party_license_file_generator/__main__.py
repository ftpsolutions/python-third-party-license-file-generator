# -*- coding: utf-8 -*-

import argparse
import codecs
import datetime
import os
import sys

import requests
import yaml
from third_party_license_file_generator.site_packages import SitePackages

# for Python2.7
try:
    reload(sys)
    sys.setdefaultencoding('utf-8')
except Exception:
    pass

parser = argparse.ArgumentParser(
    prog='python -m third_party_license_file_generator',
    description=(
        'A tool that looks at pip requirements, virtualenv site-packages, PyPI and Github to build up '
        'information about licenses for a project. You can specify multiple instances of requirements '
        'paths, Python executables, GPL-licensed exceptions and Commercially-licensed exceptions'
    )
)

parser.add_argument(
    '-r',
    '--requirements-path',
    action='append',
    required=True,
    help='a pip requirements file to use'
)

parser.add_argument(
    '-p',
    '--python-path',
    action='append',
    required=True,
    help='a Python executable to link to the requirements file'
)

parser.add_argument(
    '-g',
    '--permit-gpl',
    action='store_true',
    required=False,
    help='permit the use of GPL-licensed packages',
)

parser.add_argument(
    '-x',
    '--gpl-exception',
    action='append',
    required=False,
    default=[],
    help='a package that is permitted, despite being GPL-licensed (only relevant if --permit-gpl is not set)',
)

parser.add_argument(
    '-c',
    '--permit-commercial',
    action='store_true',
    required=False,
    help='permit the use of Comercially-licensed packages',
)

parser.add_argument(
    '-y',
    '--commercial-exception',
    action='append',
    required=False,
    default=[],
    help='a package that is permitted, despite being Commercially-licensed (only relevant if --permit-commercial is not set)',
)

parser.add_argument(
    '-s',
    '--skip-prefix',
    action='append',
    required=False,
    default=None,
    help='a module prefix that\'ll be skipped for all processing (e.g. ims-)',
)

parser.add_argument(
    '-o',
    '--output-file',
    type=str,
    required=False,
    default='THIRDPARTYLICENSES',
    help='the output text file (default THIRDPARTYLICENSES in this folder)'
)

parser.add_argument(
    '-n',
    '--no-internet-lookups',
    action='store_true',
    required=False,
    help=(
        'disable accessing PyPI and Github to get further licenses detail (if missing from site-packages folder); '
        'PLEASE NOTE that you will likely get lots of packages falsely identified as commercial (due to missing '
        'license info locally)'
    )
)

parser.add_argument(
    '-l',
    '--license-override-file',
    type=str,
    required=False,
    default=None,
    help='the location of a YAML file that describes a dict {"(some case-sensitive package name)": {"license_name": "(some license name)", "license_file": "(URL or system file path to license file"}} (but as YAML)'
)


if __name__ == '__main__':
    args = parser.parse_args()

    license_overrides = {}
    if args.license_override_file is not None:
        with codecs.open(args.license_override_file, 'r', 'utf-8') as f:
            license_overrides = yaml.load(f.read())

        for module_name, license_override in license_overrides.items():
            license_name = license_override.get('license_name')
            license_file = license_override.get('license_file')
            if None in [license_name, license_file]:
                print(
                    'ERROR: license_name or license_file for license override of {0} missing or empty'.format(
                        repr(module_name)
                    )
                )
                sys.exit(1)

            actual_license_file = None
            if license_file.lower().startswith('http'):
                r = requests.get(license_file, timeout=5)
                actual_license_file = r.text.strip()
            else:
                with codecs.open(license_file, 'r', 'utf-8') as f:
                    actual_license_file = f.read().strip()

            if actual_license_file is None:
                print(
                    'ERROR: attempt to get license_file for license override of {0} from {1} returned empty file'.format(
                        repr(module_name),
                        repr(license_file)
                    )
                )
                sys.exit(1)

            license_override['license_file'] = actual_license_file

    pairs = tuple(
        zip(
            [x.strip() for x in args.requirements_path if x.strip() != ''],
            [x.strip() for x in args.python_path if x.strip() != ''],
        )
    )

    print('mixing requirements paths and Python paths together as follows:')

    for pair in pairs:
        print('\t{0} - {1}'.format(
            repr(pair[0]),
            repr(pair[1]),
        ))

    print('\nworking on license summary...\n')

    site_packages = []
    for requirements_path, python_path in pairs:
        print('handling {0} with {1} ...'.format(
            repr(requirements_path),
            repr(python_path)
        ))

        site_packages += [
            SitePackages(
                requirements_path=requirements_path,
                python_path=python_path,
                skip_prefixes=args.skip_prefix,
                use_internet=not args.no_internet_lookups,
                license_overrides=license_overrides,
            )
        ]

    joined = site_packages[0]
    for x in site_packages[1:]:
        joined += x

    print('')

    gpl_warning = ' <---- !!! WARNING: you have specified not to permit GPL licenses but GPL-licensed packages were detected'
    commercial_warning = ' <---- !!! WARNING: you have specified not to permit Commercial licenses but Comercially-licensed packages were detected'

    gpl_triggered = False
    commercial_triggered = False

    for license_name, modules in sorted(joined.modules_by_license_name.items()):
        module_output = ''
        module_names = []
        for module in modules:
            module_names += [module.name]
            module_output += '\t{0} by {1} ({2})\n'.format(
                repr(module.name),
                repr(module.author),
                repr(module.home_page),
            )

        warning = ''
        if not args.permit_gpl and license_name.startswith('GPL') and not all(
                [x in args.gpl_exception for x in module_names]):
            warning = gpl_warning
            gpl_triggered = True
        elif not args.permit_commercial and license_name in ['Commercial', 'Unknown (assumed commercial)']:
            warning = commercial_warning
            commercial_triggered = True

        print('{0}{1}\n{2}'.format(
            license_name, warning, module_output
        ))

    if gpl_triggered or commercial_triggered:
        print(
            'ERROR: One or more conditions were triggered (e.g. GPL-licensed/Commercially licensed packages detected; cannot continue'
        )
        exit(1)

    print('\nworking on {0}...\n'.format(args.output_file))

    third_party_licenses = []

    third_party_licenses += [
        u'Start of {0} generated by Python third_party_license_generator at {1}'.format(
            repr(os.path.split(args.output_file)[-1]),
            datetime.datetime.now()
        )
    ]

    for _, module in sorted(joined.modules_by_module_name.items()):
        blurb = u'Package: {0}\nLicense: {1}\nRequires: {2}\nAuthor: {3}\nHome page: {4}\n\n'.format(
            module.name,
            module.license_name,
            ', '.join(module.requires) if len(module.requires) > 0 else 'n/a',
            module.author,
            module.home_page,
        )

        blurb += u'{0}'.format(
            module.license_file
        )

        third_party_licenses += [blurb.strip()]

    third_party_licenses += [
        u'End of {0} generated by Python third_party_license_generator at {1}'.format(
            repr(os.path.split(args.output_file)[-1]),
            datetime.datetime.now()
        )
    ]

    separator = u'-' * 40

    data = u'\n\n{0}\n\n'.format(separator).join(third_party_licenses)

    with codecs.open(args.output_file, 'w', 'utf-8') as f:
        f.write(data.strip() + '\n')

    print('Done; see output at {0}'.format(repr(args.output_file)))
