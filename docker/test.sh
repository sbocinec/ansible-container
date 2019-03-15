#!/bin/bash
set -e

usage() {
  echo "$0 -d <distro name>"
  echo
  echo "Example: $0 -d slim"
  exit 0
}

while getopts "d:" opt; do
  case $opt in
    d)
      # name of the distro to build, e.g. slim, alpine
      distro=$OPTARG
      ;;
    *)
      usage
      ;;
  esac
done


SCRIPT_DIR=$(dirname "${BASH_SOURCE[0]}")
cd "${SCRIPT_DIR}"

IMAGE_NAME="sbocinec/ansible-container"
if [ "${DOCKER_REPO}" ]; then
  IMAGE_NAME="${DOCKER_REPO}"
elif [ "${PROJECT_PATH}" ]; then
  IMAGE_NAME="${PROJECT_PATH}"
fi

if [ -f ANSIBLE_VERSION ]; then
  while read version; do
    if [[ "$version" =~ ^[0-9]+.[0-9]+.*$ ]]; then
      docker run -t --rm ${IMAGE_NAME}:${version}-${distro} |grep '^ansible-playbok' |grep $version
    fi
  done < ANSIBLE_VERSION
fi
