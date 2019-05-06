#!/usr/bin/env python3

import argparse
import json
import re
import requests
import subprocess
import sys
from distutils.version import StrictVersion

# latest_version = ''
# latest_versions = {}
# build_versions = {}

class Github:
    def __init__(self, project):
        self.project = project
        self.release_tags = []


    def github_get_release_tags(self):
        github_url = 'https://api.github.com/repos/{}/tags'.format(self.project)
        github_headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        req = requests.get(github_url, headers=github_headers)
        req.raise_for_status()
        self.release_tags = [tag['name'] for tag in req.json()]


class Ansible(Github):
    def __init__(self, project):
        super().__init__(project)
        self.latest_version = ''
        self.latest_versions = {}
        self.build_candidates = {}


class Docker:
    def __init__(self, docker_image):
        self.docker_image = docker_image
        self.docker_image_tags = []


    def __hub_auth(self):
        """Get Docker Hub auth token"""
        docker_hub_auth_url = 'https://auth.docker.io/token?scope=repository:{}:pull&service=registry.docker.io'.format(self.docker_image)
        req = requests.get(docker_hub_auth_url)
        req.raise_for_status()
        return req.json()['token']


    def hub_get_image_tags(self, os):
        """Get docker image tags for the docker_image repository"""
        token = self.__hub_auth()
        docker_hub_registry_url = 'https://registry-1.docker.io/v2/{}/tags/list'.format(self.docker_image)
        docker_hub_auth_headers = {
            'Accept': 'application/vnd.docker.distribution.manifest.v2+json',
            'Authorization': 'Bearer {}'.format(token)
        }
        req = requests.get(docker_hub_registry_url, headers=docker_hub_auth_headers)
        req.raise_for_status()
        matcher = re.compile(r'^(\d+\.\d+\.\d+)-{}$'.format(os))
        self.docker_image_tags = [ver.strip('-{}'.format(os)) for ver in list(filter(matcher.search, req.json()['tags']))]


def compare_version_higher(ver1, ver2):
    match = []
    matcher = re.compile(r'^(\d+\.\d+)\.(\d+)$')
    match = [re.match(matcher, ver1), re.match(matcher, ver2)]
    if int(match[0].group(2)) > int(match[1].group(2)):
        return True
    else:
        return False


def normalize_version(version):
    """
    Normalize version string - strip 'v' prefix and return a list of 2 elements
    """

    matcher = re.compile(r'^v?((\d+\.\d+).\d+)$')
    match = re.match(matcher, version)
    if match is not None:
        return [match.group(1), match.group(2)]
    else:
        return [None, None]


def find_majmin_tags(ver_dict, ver_list):
    for ver_el in ver_list:
        ver_full, ver_maj = normalize_version(ver_el)
        if ver_full is not None:
            if ver_maj in ver_dict:
                if compare_version_higher(ver_full, ver_dict[ver_maj]):
                    ver_dict[ver_maj] = ver_full
            else:
                ver_dict[ver_maj] = ver_full
    return ver_dict


def find_latest(versions):
    latest = None
    if len(versions) == 1:
        return versions[0]
    else:
        latest = versions[0]
        for version in versions[1:]:
            if StrictVersion(version) > StrictVersion(latest):
                latest = version
    return latest


def check_version(ansible_tags, docker_tags):
    # find ansible versions that do not have docker image created
    for ansible_tag in ansible_tags:
        ver_full, ver_maj = normalize_version(ansible_tag)
        if ver_full is not None:
            print('Checking ansible_tag: "{}"'.format(ver_full))
            if ver_full in docker_tags:
                print("{} image already exists in docker hub".format(ver_full))
            else:
                print("{} image does not exist in docker hub, building".format(ver_full))
                build_candidates[ver_full] = True


def run_command(cmd, dry_run=False):
    # runs a command and return the subprocess.run returncode
    print(cmd)
    if dry_run:
        return 0
    else:
        run = subprocess.run(cmd, shell=True, check=False)
        return run.returncode


def build_images(images, repo, os):
    for image in images:
        cmd = 'docker build --build-arg=ANSIBLE_VERSION={} -t {}:{}-{} {}/'.format(image, repo, image, os, os)
        if run_command(cmd, args.dry_run) != 0:
            images[image] = False
            next

    return images


def test_images(images, repo, os):
    for image in images:
        if images[image]:
            cmd = "docker run --rm {}:{}-{} |awk '/^ansible-playbook/ {{ print $2 }}' |grep {}".format(repo, image, os, image)
            if run_command(cmd, args.dry_run) != 0:
                images[image] = False
                next

    return images


def tag_images(images, repo, os, latest, latest_dict, latest_value):
    # tags newly created docker images and pushes it to the docker hub
    for image in images:
        if images[image]:
            # Pushing major.minor.patch-distro
            cmd = 'docker push {}:{}-{}'.format(repo, image, os)
            if run_command(cmd, args.dry_run) != 0:
                images[image] = False
                next
            ver_full, ver_maj = normalize_version(image)
            if latest:
                # major.minor.patch
                cmd = 'docker tag {}:{}-{} {}:{}'.format(repo, image, os, repo, image)
                if run_command(cmd, args.dry_run) != 0:
                    images[image] = False
                    next
                cmd = 'docker push {}:{}'.format(repo, image)
                if run_command(cmd, args.dry_run) != 0:
                    images[image] = False
                    next
                if latest_dict[ver_maj] == image:
                    # major.minor
                    cmd = 'docker tag {}:{}-{} {}:{}'.format(repo, image, os, repo, ver_maj)
                    if run_command(cmd, args.dry_run) != 0:
                        images[image] = False
                        next
                    cmd = 'docker push {}:{}'.format(repo, ver_maj)
                    if run_command(cmd, args.dry_run) != 0:
                        images[image] = False
                        next
                    # major.minor-os
                    cmd = 'docker tag {}:{}-{} {}:{}-{}'.format(repo, image, os, repo, ver_maj, os)
                    if run_command(cmd, args.dry_run) != 0:
                        images[image] = False
                        next
                    cmd = 'docker push {}:{}-{}'.format(repo, ver_maj, os)
                    if run_command(cmd, args.dry_run) != 0:
                        images[image] = False
                        next
                if image == latest_value:
                    # latest
                    cmd = 'docker tag {}:{}-{} {}:latest'.format(repo, image, os, repo)
                    if run_command(cmd, args.dry_run) != 0:
                        images[image] = False
                        next
                    cmd = 'docker push {}:latest'.format(repo)
                    if run_command(cmd, args.dry_run) != 0:
                        images[image] = False
                        next
                    # os
                    cmd = 'docker tag {}:{}-{} {}:{}'.format(repo, image, os, repo, os)
                    if run_command(cmd, args.dry_run) != 0:
                        images[image] = False
                        next
                    cmd = 'docker push {}:{}'.format(repo, os)
                    if run_command(cmd, args.dry_run) != 0:
                        images[image] = False
                        next
            else:
                if latest_dict[ver_maj] == image:
                    # major.minor-os
                    cmd = 'docker tag {}:{}-{} {}:{}-{}'.format(repo, image, os, repo, ver_maj, os)
                    if run_command(cmd, args.dry_run) != 0:
                        images[image] = False
                        next
                    cmd = 'docker push {}:{}-{}'.format(repo, ver_maj, os)
                    if run_command(cmd, args.dry_run) != 0:
                        images[image] = False
                        next

    return images


parser = argparse.ArgumentParser(description='Build and push Ansible docker images')
parser.add_argument('-o', '--os', default='slim',
    help="name of the distro to build, e.g. slim, alpine", required=True)
parser.add_argument('-l', '--latest', action="store_true",
    help="latest flag specifies whether default docker tags should be applied (latest)")
parser.add_argument('-r', '--repo-name', default='sbocinec/ansible', type=str,
    help="Docker repository name, i.e. sbocinec/ansible")
parser.add_argument('-a', '--ansible-name', default='ansible/ansible', type=str,
    help="Ansible GitHub repository name, i.e. ansible/ansible")
parser.add_argument('-d', '--dry-run', action="store_true",
    help="Dry run build script without any modifications")
args = parser.parse_args()

docker = Docker(args.repo_name)
docker.hub_get_image_tags(args.os)

ansible =  Ansible(args.ansible_name)
ansible.github_get_release_tags()

ansible.latest_versions = find_majmin_tags(ansible.latest_versions, docker.docker_image_tags)
check_version(ansible.release_tags, docker.docker_image_tags)
build_candidates = build_images(build_candidates, args.repo_name, args.os)
build_candidates = test_images(build_candidates, args.repo_name, args.os)
latest_versions = find_majmin_tags(latest_versions, [key for key in build_candidates if build_candidates[key]])
latest_version = find_latest(list(latest_versions.values()))

build_candidates = tag_images(build_candidates, args.repo_name, args.os, args.latest, latest_versions, latest_version)

failed_builds = [key for key in build_candidates if not build_candidates[key]]
if len(failed_builds) > 0:
    print('Failed to build docker images for following ansible versions: {}'.format(failed_builds))
    sys.exit(1)
