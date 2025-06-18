# Python third_party_license_file_generator

The Python third_party_license_file_generator is aimed at distilling down the appropriate license for one or many pip "requirements" files into a single file; it supports Python2.7 and Python3.

## Thanks to everyone who has contributed over the years!

- [fredvisser](https://github.com/fredvisser)
- [Brian-Williams](https://github.com/Brian-Williams)
- [andzn](https://github.com/andzn)
- [dave-v](https://github.com/dave-v)
- [j-b-d](https://github.com/j-b-d)
- [malesh](https://github.com/malesh)
- [lowaa](https://github.com/lowaa)

## How do I install it?

    $ pip install third-party-license-file-generator

## How do I use it?

    $ python -m third_party_license_file_generator -h

## How does it work?

With no arguments (other than a pip "requirements" file and a Python executable path that has those requirements installed), the process is as follows:

- walk the given Python executable's site-packages folder and build up package metadata (and license files, if present)
- filter down by packages that are listed in the pip "requirements" file (and those packages dependencies, and their dependencies, and their dependencies... you get the gist)
  - note: it follows "-r some_file.txt" references found in the pip "requirements" files
- if a license name could not be secured for a package, try to gather that from the package's PyPI web page
  - if a license name has still not been secured and the package lists a GitHub home page, try to find a license from there
    - otherwise, assume the package to be commercially licensed (as it is legally understood that is the case)
- if a license file could not be secured for a package and the package lists a GitHub home page, try to find a license from there
  - otherwise, create a license (for the known license name) from a local collection of licenses (within the Python Third Party License Generator)
- show a summary of packages against licenses to the user
- build a THIRDPARTYLICENSES file in the current folder
- give a return code of zero for success or non-zero for failures (e.g. GPL-licensed packages detected when specified to not permit GPL)

It's worth noting that information learned about packages is cached- so if you have to build one third party licenses file for a large project that has many components with many dependencies (but some overlap) then it's best to specify all those pip "requirements" files and Python executable paths in a single call to the Python third_party_license_file_generator as it will take less time overall.

You can specify a number of command line options (check syntax with -h) to do things like the following:

- handle multiple pip "requirements" files
- handle multiple Python executable paths
- whether or not to permit GPL-licensed packages (default no)
- specific GPL-licensed package exceptions (e.g. if a package lists exceptions to the GPL that may suit your needs but is still GPL-licensed)
- whether or not to permit comercially-licensed packages (default no)
- specific comercially-licensed package exceptions (e.g. if you have a license for a package or if you own a package)
- a "skip prefix" (e.g. if you want to skip all packages starting with a certain string)
- disable internet lookups (if you don't want to pull data from PyPI and GitHub)
- disable skipping of not required packages (packages that are not requirements of other packages are skipped by default during license file generation)

## Examples

Two different pip "requirements" files, two different Python paths (Virtualenvs) and a skip prefix:

    python -m third_party_license_file_generator \
        -r requirements-py.txt \
        -p ~/.virtualenvs/backend_py/bin/python \
        -r requirements-pypy.txt \
        -p ~/.virtualenvs/backend_pypy/bin/python \
        -s ims-

Please note that pip "requirements" files and Python executable paths are paired together in the order they're specified.

Three different pip "requirements" files, two different Python paths (need to repeat), a GPL exception and a custom output file:

    python -m third_party_license_file_generator \
        -r requirements.txt \
        -p ~/.virtualenvs/api_pypy/bin/python \
        -r pypy_requirements.txt \
        -p ~/.virtualenvs/api_pypy/bin/python \
        -r cpython_requirements.txt \
        -p ~/.virtualenvs/api_py/bin/python \
        -x uWSGI \
        -o ThirdPartyLicenses.txt

Three different pip "requirements" files, two different Python paths (need to repeat), a GPL exception, a custom output file and a license override file:

    # contents of license_override_file.yml
    uWSGI:
        license_name: GPL-2.0 w/ linking exception
        license_file: https://raw.githubusercontent.com/unbit/uwsgi/master/LICENSE

    python -m third_party_license_file_generator \
        -r requirements.txt \
        -p ~/.virtualenvs/api_pypy/bin/python \
        -r pypy_requirements.txt \
        -p ~/.virtualenvs/api_pypy/bin/python \
        -r cpython_requirements.txt \
        -p ~/.virtualenvs/api_py/bin/python \
        -x uWSGI \
        -o ThirdPartyLicenses.txt \
        -l license_override_file.yml

An example of the structure of the generated third party license file is as follows:

    Start of 'ThirdPartyLicenses.txt' generated by Python third_party_license_generator at 2018-04-19 12:36:58.627421

    ----------------------------------------

    Package: Django
    License: BSD-3-clause
    Requires: pytz
    Author: Django Software Foundation <foundation@djangoproject.com>
    Home page: https://www.djangoproject.com/

    (license content appears here in full)

    ----------------------------------------

    End of 'ThirdPartyLicenses.txt' generated by Python third_party_license_generator at 2018-04-19 12:36:58.627825

## Packaging notes

### Testing

If you're making any changes you can run the tests:

```bash
./test.sh
```

### Publishing

NOTE: This probably only applies to folks that work at [FTP Solutions](https://github.com/ftpsolutions/) (maintainers of this package).

This will test a few Python versions, operating the tool against this repo's `requirements.txt`.

When you're ready to push to PyPI, as long as you have a `~/.pypirc` and you have permissions to push to the repo:

```bash
./build-tag-and-push.sh
```
