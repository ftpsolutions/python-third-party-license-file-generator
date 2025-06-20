#!/bin/bash

set -e

python_version="3.12"
image_base="$(basename "$(pwd)")-build-tag-and-push"
image="${image_base}:${python_version}"
container="${image_base}-${python_version}"

if ! test -e "${HOME}/.pypirc"; then
    echo "error: failed to find ${HOME}/.pypirc"
    exit 1
fi

docker build --build-arg "VERSION=${python_version}" -f ./Dockerfile -t "${image}" .

command="python setup.py sdist && ls -al dist/* && twine upload dist/*"
if [[ "${SKIP_PUSH}" == "1" ]]; then
    command="python setup.py sdist && ls -al dist/*"
fi

docker run --rm --name "${container}" -v "${HOME}/.pypirc:/root/.pypirc" --workdir "/srv/python-third-party-license-file-generator" --entrypoint bash "${image}" -c "${command}"
