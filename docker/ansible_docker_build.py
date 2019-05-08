#!/usr/bin/env python3

import argparse
import json
import re
import requests
import subprocess
import sys
from distutils.version import StrictVersion

class GitHub:
    def __init__(self, project):
        self.project = project
        self.release_tags = []


    def get_release_tags(self):
        github_url = 'https://api.github.com/repos/{}/tags'.format(self.project)
        github_headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        req = requests.get(github_url, headers=github_headers)
        req.raise_for_status()
        self.release_tags = [tag['name'] for tag in req.json()]


class Docker:
    def __init__(self, repository, os, is_latest):
        self.repository = repository
        self.os = os
        self.is_latest = is_latest
        self.docker_image_tags = []
        self.latest_versions = {}
        self.image_build_status = {}


    def __hub_auth(self):
        """Get Docker Hub auth token"""
        docker_hub_auth_url = 'https://auth.docker.io/token?scope=repository:{}:pull&service=registry.docker.io'.format(self.repository)
        req = requests.get(docker_hub_auth_url)
        req.raise_for_status()
        return req.json()['token']


    def get_hub_image_tags(self):
        """Get docker image tags for the docker_image repository"""
        token = self.__hub_auth()
        docker_hub_registry_url = 'https://registry-1.docker.io/v2/{}/tags/list'.format(self.repository)
        docker_hub_auth_headers = {
            'Accept': 'application/vnd.docker.distribution.manifest.v2+json',
            'Authorization': 'Bearer {}'.format(token)
        }
        req = requests.get(docker_hub_registry_url, headers=docker_hub_auth_headers)
        req.raise_for_status()
        matcher = re.compile(r'^(\d+\.\d+\.\d+)-{}$'.format(self.os))
        self.docker_image_tags = [ver.strip('-{}'.format(self.os)) for ver in list(filter(matcher.search, req.json()['tags']))]


    def find_build_candidates(self, ansible_tags):
        """Find ansible versions that do not have docker image created"""
        for ansible_tag in ansible_tags:
            version_full, _ = normalize_version(ansible_tag)
            if version_full is not None:
                print('Checking if docker image exists for ansible_tag: "{}"'.format(version_full))
                if version_full in self.docker_image_tags:
                    print("Docker image {} already exists in docker hub".format(version_full))
                else:
                    print("Docker image {} does not exist in docker hub, building".format(version_full))
                    self.image_build_status[version_full] = True


    def build_images(self):
        """Build docker images"""
        self.image_build_status
        for image in self.image_build_status:
            cmd = 'docker build --build-arg=ANSIBLE_VERSION={} -t {}:{}-{} {}/'.format(image, self.repository, image, self.os, self.os)
            if run_command(cmd, args.dry_run) != 0:
                self.image_build_status[image] = False
                next


    def test_images(self):
        """Test new built images"""
        for image in self.image_build_status:
            if self.image_build_status[image]:
                cmd = "docker run --rm {}:{}-{} |awk '/^ansible-playbook/ {{ print $2 }}' |grep {}".format(self.repository, image, self.os, image)
                if run_command(cmd, args.dry_run) != 0:
                    self.image_build_status[image] = False
                    next



    def tag_images(self):
        """Tag newly built docker images and push them to the docker hub"""
        maj_min_versions = find_majmin_versions(list(set(self.docker_image_tags + [key for key in self.image_build_status if self.image_build_status[key]])))
        latest_version = find_latest(list(maj_min_versions.values()))

        for image in self.image_build_status:
            if self.image_build_status[image]:
                # Pushing major.minor.patch-distro
                cmd = 'docker push {}:{}-{}'.format(self.repository, image, self.os)
                if run_command(cmd, args.dry_run) != 0:
                    self.image_build_status[image] = False
                    next
                _ , version_major = normalize_version(image)
                if self.is_latest:
                    # major.minor.patch
                    cmd = 'docker tag {}:{}-{} {}:{}'.format(self.repository, image, self.os, self.repository, image)
                    if run_command(cmd, args.dry_run) != 0:
                        self.image_build_status[image] = False
                        next
                    cmd = 'docker push {}:{}'.format(self.repository, image)
                    if run_command(cmd, args.dry_run) != 0:
                        self.image_build_status[image] = False
                        next
                    if maj_min_versions[version_major] == image:
                        # major.minor
                        cmd = 'docker tag {}:{}-{} {}:{}'.format(self.repository, image, self.os, self.repository, version_major)
                        if run_command(cmd, args.dry_run) != 0:
                            self.image_build_status[image] = False
                            next
                        cmd = 'docker push {}:{}'.format(self.repository, version_major)
                        if run_command(cmd, args.dry_run) != 0:
                            self.image_build_status[image] = False
                            next
                        # major.minor-os
                        cmd = 'docker tag {}:{}-{} {}:{}-{}'.format(self.repository, image, self.os, self.repository, version_major, self.os)
                        if run_command(cmd, args.dry_run) != 0:
                            self.image_build_status[image] = False
                            next
                        cmd = 'docker push {}:{}-{}'.format(self.repository, version_major, self.os)
                        if run_command(cmd, args.dry_run) != 0:
                            self.image_build_status[image] = False
                            next
                    if latest_version == image:
                        # latest
                        cmd = 'docker tag {}:{}-{} {}:latest'.format(self.repository, image, self.os, self.repository)
                        if run_command(cmd, args.dry_run) != 0:
                            self.image_build_status[image] = False
                            next
                        cmd = 'docker push {}:latest'.format(self.repository)
                        if run_command(cmd, args.dry_run) != 0:
                            self.image_build_status[image] = False
                            next
                        # os
                        cmd = 'docker tag {}:{}-{} {}:{}'.format(self.repository, image, self.os, self.repository, self.os)
                        if run_command(cmd, args.dry_run) != 0:
                            self.image_build_status[image] = False
                            next
                        cmd = 'docker push {}:{}'.format(self.repository, self.os)
                        if run_command(cmd, args.dry_run) != 0:
                            self.image_build_status[image] = False
                            next
                else:
                    if maj_min_versions[version_major] == image:
                        # major.minor-os
                        cmd = 'docker tag {}:{}-{} {}:{}-{}'.format(self.repository, image, self.os, self.repository, version_major, self.os)
                        if run_command(cmd, args.dry_run) != 0:
                            self.image_build_status[image] = False
                            next
                        cmd = 'docker push {}:{}-{}'.format(self.repository, version_major, self.os)
                        if run_command(cmd, args.dry_run) != 0:
                            self.image_build_status[image] = False
                            next


    def get_build_status(self):
        return self.image_build_status


def is_version_higher(ver1, ver2):
    match = []
    matcher = re.compile(r'^(\d+\.\d+)\.(\d+)$')
    match = [re.match(matcher, ver1), re.match(matcher, ver2)]
    if int(match[0].group(2)) > int(match[1].group(2)):
        return True
    else:
        return False


def normalize_version(version):
    """Normalize version string - strip 'v' prefix and return a list of 2 elements"""

    matcher = re.compile(r'^v?((\d+\.\d+).\d+)$')
    match = re.match(matcher, version)
    if match is not None:
        return [match.group(1), match.group(2)]
    else:
        return [None, None]


def find_majmin_versions(versions):
    major_minor_versions = {}
    for version in versions:
        version_full, version_major = normalize_version(version)
        if version_full is not None:
            if version_major in major_minor_versions:
                if is_version_higher(version_full, major_minor_versions[version_major]):
                    major_minor_versions[version_major] = version_full
            else:
                major_minor_versions[version_major] = version_full
    return major_minor_versions


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


def run_command(cmd, dry_run=False):
    # run a command and return the subprocess.run.returncode
    print(cmd)
    if dry_run:
        return 0
    else:
        run = subprocess.run(cmd, shell=True, check=False)
        return run.returncode



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

build_status = {}

ansible = GitHub(args.ansible_name)
ansible.get_release_tags()

docker = Docker(args.repo_name, args.os, args.latest)
docker.get_hub_image_tags()
docker.find_build_candidates(ansible.release_tags)
docker.build_images()
docker.test_images()
docker.tag_images()
build_status = docker.get_build_status()
failed_builds = [key for key in build_status if not build_status[key]]
if len(failed_builds) > 0:
    print('Failed to build docker images for following ansible versions: {}'.format(failed_builds))
    sys.exit(1)
