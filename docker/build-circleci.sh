#!/bin/bash
set -e

latest=false

usage() {
  echo "$0 -d <distro name> [-l]"
  echo
  echo "Example: $0 -d slim -l"
  exit 0
}

while getopts "d:l" opt; do
  case $opt in
    d)
      # name of the distro to build, e.g. slim, alpine
      distro=$OPTARG
      ;;
    l)
      # latest/default flag
      default=true
      ;;
    *)
      usage
      ;;
  esac
done

IMAGE_NAME="sbocinec/ansible"
if [ "${CI_REGISTRY_IMAGE}" ]; then
  IMAGE_NAME="${CI_REGISTRY_IMAGE}"
elif [ "${DOCKER_REPO}" ]; then
  IMAGE_NAME="${DOCKER_REPO}"
elif [ "${CCI_IMAGE}" ]; then
  IMAGE_NAME="${CCI_IMAGE}"
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/ && pwd )"
cd "${SCRIPT_DIR}/$distro"

if [ -f "${SCRIPT_DIR}/ANSIBLE_VERSION" ]; then
  count=0
  while read version; do
    if [[ "$version" =~ ^[0-9]+.[0-9]+.*$ ]]; then
      (( count+=1 ))
      docker build --build-arg=ANSIBLE_VERSION=$version -t ${IMAGE_NAME}:${version}-${distro} .
      # docker run -t --rm ${IMAGE_NAME}:${version}-${distro} |grep '^ansible-playbok' |grep $version
      docker push ${IMAGE_NAME}:${version}-${distro}
      if [ "$default" = true ]; then
        docker tag ${IMAGE_NAME}:${version}-${distro} ${IMAGE_NAME}:$version
        docker push ${IMAGE_NAME}:${version}
        if [ "$count" -eq "1" ]; then
          # tag only newest version
          docker tag ${IMAGE_NAME}:${version}-${distro} ${IMAGE_NAME}:latest
          docker push ${IMAGE_NAME}:latest
          docker tag ${IMAGE_NAME}:${version}-${distro} ${IMAGE_NAME}:$distro
          docker push ${IMAGE_NAME}:$distro
        fi
      else
        if [ "$count" -eq "1" ]; then
          # tag only newest version
          docker tag ${IMAGE_NAME}:${version}-${distro} ${IMAGE_NAME}:$distro
          docker push ${IMAGE_NAME}:$distro
        fi
      fi
    fi
  done < "${SCRIPT_DIR}/ANSIBLE_VERSION"
fi
