#!/bin/bash

set -e

image_base="$(basename "$(pwd)")-test"

VERSIONS=${VERSIONS:-"2.7 3.9 3.12 3.13 3.14"}

PLATFORM="${PLATFORM:-}"
platform_arg=""
if [[ "${PLATFORM}" != "" ]]; then
	platform_arg="--platform=${PLATFORM}"
fi

ATTACH="${ATTACH:-0}"

for version in ${VERSIONS}; do
	image="${image_base}:${version}"

	echo ""
	echo "!!!!"
	echo "!!!! building ${image}"
	echo "!!!!"
	echo ""

	# shellcheck disable=SC2086
	if ! docker build ${platform_arg} --build-arg "VERSION=${version}" -f ./Dockerfile -t "${image}" .; then
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

	if [[ "${ATTACH}" == "1" ]]; then
		# shellcheck disable=SC2086
		if ! docker run ${platform_arg} --rm -it --name "${container}" --workdir /test --entrypoint bash "${image}"; then
			echo "error: failed to run ${image}"
			exit 1
		fi
	fi

	# shellcheck disable=SC2086
	if ! docker run ${platform_arg} --rm --name "${container}" --workdir /test "${image}"; then
		echo "error: failed to run ${image}"
		exit 1
	fi
done
