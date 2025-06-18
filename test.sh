#!/bin/bash

set -e

image_base="$(basename "$(pwd)")-test"

VERSIONS=${VERSIONS:-"2.7 3.9 3.12 3.13"}

for version in ${VERSIONS}; do
    image="${image_base}:${version}"

    echo ""
    echo "!!!!"
    echo "!!!! building ${image}"
    echo "!!!!"
    echo ""

    if ! docker build --build-arg "VERSION=${version}" -f ./Dockerfile -t "${image}" .; then
        echo "error: failed to build ${image}"
        exit 1
    fi
done

for version in ${VERSIONS}; do
    container="${image_base}-${version}"
    image="${image_base}:${version}"

    echo ""
    echo "!!!!"
    echo "!!!! running ${image}"
    echo "!!!!"
    echo ""

    if ! docker run --rm --name "${container}" --workdir /test "${image}"; then
        echo "error: failed to run ${image}"
        exit 1
    fi
done
