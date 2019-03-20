#!/usr/bin/env python3

import argparse
import json
import re
import requests
import subprocess
import sys
from distutils.version import StrictVersion

docker_image_tags = []
ansible_release_tags = []
latest_version = ''
latest_versions = {}
build_versions = {}

def docker_hub_auth(image_name):
    docker_hub_auth_url = 'https://auth.docker.io/token?scope=repository:{}:pull&service=registry.docker.io'.format(image_name)
    req = requests.get(docker_hub_auth_url)
    req.raise_for_status()
    return req.json()['token']


def docker_hub_get_image_tags(image_name, token):
    docker_hub_registry_url = 'https://registry-1.docker.io/v2/{}/tags/list'.format(image_name)
    docker_hub_auth_headers = {
        'Accept': 'application/vnd.docker.distribution.manifest.v2+json',
        'Authorization': 'Bearer {}'.format(token)
    }
    req = requests.get(docker_hub_registry_url, headers=docker_hub_auth_headers)
    req.raise_for_status()
    return req.json()['tags']


def github_get_project_tags(project_name):
    tags = []
    github_url = 'https://api.github.com/repos/{}/tags'.format(project_name)
    github_headers = {
        'Accept': 'application/vnd.github.v3+json'
    }
    req = requests.get(github_url, headers=github_headers)
    req.raise_for_status()
    return [tag['name'] for tag in req.json()]


def compare_version_higher(ver1, ver2):
    match = []
    matcher = re.compile(r'^(\d+\.\d+)\.(\d+)$')
    match = [re.match(matcher, ver1), re.match(matcher, ver2)]
    if int(match[0].group(2)) > int(match[1].group(2)):
        return True
    else:
        return False


def normalize_version(version):
    matcher = re.compile(r'^v?((\d+\.\d+).(\d+))$')
    match = re.match(matcher, version)
    if match is not None:
        return [match.group(1), match.group(2), match.group(3)]
    else:
        return [None, None, None]

def filter_distro_tags(tags, os):
    matcher = re.compile(r'^(\d+\.\d+\.\d+)-{}$'.format(os))
    return [ver.strip('-{}'.format(os)) for ver in list(filter(matcher.search, tags))]


def find_majmin_tags(ver_dict, ver_list):
    for ver_el in ver_list: 
        ver_full, ver_maj, ver_patch = normalize_version(ver_el)
        if ver_full is not None:
            if ver_maj in ver_dict:
                if compare_version_higher(ver_full, ver_dict[ver_maj]):
                    ver_dict[ver_maj] = ver_full
            else:
                ver_dict[ver_maj] = ver_full
    return ver_dict


def find_latest(ver_list):
    latest = None
    if len(ver_list) == 1:
        return ver_list[0]
    else:
        latest = ver_list[0]
        for ver in ver_list:
            if StrictVersion(ver) > StrictVersion(latest):
                latest = ver
    return latest


def check_version(ansible_tags, docker_tags):
    for ansible_tag in ansible_tags:
        ver_full, ver_maj, ver_patch = normalize_version(ansible_tag)
        if ver_full is not None:
            print('Checking ansible_tag: "{}"'.format(ver_full))
            if ver_full in docker_tags:
                print("{} image already exists in docker hub".format(ver_full))
            else:
                build_versions[ver_full] = True
                print("{} image does not exist in docker hub, building".format(ver_full))



def build_images(images, repo, os):
    for image in images:
        cmd = 'docker build --build-arg=ANSIBLE_VERSION={} -t {}:{}-{} {}/'.format(image, repo, image, os, os)
        print(' {}'.format(cmd))
        res = subprocess.run(cmd, shell=True, check=False)
        if res.returncode != 0:
            images[image] = False
            next

    return images


def test_images(images, repo, os):
    for image in images:
        if images[image]:
            cmd = "docker run --rm {}:{}-{} |awk '/^ansible-playbook/ {{ print $2 }}' |grep {}".format(repo, image, os, image)
            print(' {}'.format(cmd))
            res = subprocess.run(cmd, shell=True, check=False)
            if res.returncode != 0:
                images[image] = False
                next

    return images

def tag_images(images, repo, os, latest, latest_dict, latest_value):
    for image in images:
        if images[image]:
            # Pushing major.minor.patch-distro
            cmd = 'docker push {}:{}-{}'.format(repo, image, os)
            print(' {}'.format(cmd))
            res = subprocess.run(cmd, shell=True, check=False)
            if res.returncode != 0:
                images[image] = False
                next
            ver_full, ver_maj, ver_patch = normalize_version(image)
            if latest:
                # major.minor.patch
                cmd = 'docker tag {}:{}-{} {}:{}'.format(repo, image, os, repo, image)
                print(' {}'.format(cmd))
                res = subprocess.run(cmd, shell=True, check=False)
                if res.returncode != 0:
                    images[image] = False
                    next
                cmd = 'docker push {}:{}'.format(repo, image)
                print(' {}'.format(cmd))
                res = subprocess.run(cmd, shell=True, check=False)
                if res.returncode != 0:
                    images[image] = False
                    next
                if latest_dict[ver_maj] == image:
                    # major.minor
                    cmd = 'docker tag {}:{}-{} {}:{}'.format(repo, image, os, repo, ver_maj)
                    print(' {}'.format(cmd))
                    res = subprocess.run(cmd, shell=True, check=False)
                    if res.returncode != 0:
                        images[image] = False
                        next
                    cmd = 'docker push {}:{}'.format(repo, ver_maj)
                    print(' {}'.format(cmd))
                    res = subprocess.run(cmd, shell=True, check=False)
                    if res.returncode != 0:
                        images[image] = False
                        next
                    # major.minor-os
                    cmd = 'docker tag {}:{}-{} {}:{}-{}'.format(repo, image, os, repo, ver_maj, os)
                    print(' {}'.format(cmd))
                    res = subprocess.run(cmd, shell=True, check=False)
                    if res.returncode != 0:
                        images[image] = False
                        next
                    cmd = 'docker push {}:{}-{}'.format(repo, ver_maj, os)
                    print(' {}'.format(cmd))
                    res = subprocess.run(cmd, shell=True, check=False)
                    if res.returncode != 0:
                        images[image] = False
                        next
                if image == latest_value:
                    # latest
                    cmd = 'docker tag {}:{}-{} {}:latest'.format(repo, image, os, repo)
                    print(' {}'.format(cmd))
                    res = subprocess.run(cmd, shell=True, check=False)
                    if res.returncode != 0:
                        images[image] = False
                        next
                    cmd = 'docker push {}:latest'.format(repo)
                    print(' {}'.format(cmd))
                    res = subprocess.run(cmd, shell=True, check=False)
                    if res.returncode != 0:
                        images[image] = False
                        next
                    # os
                    cmd = 'docker tag {}:{}-{} {}:{}'.format(repo, image, os, repo, os)
                    print(' {}'.format(cmd))
                    res = subprocess.run(cmd, shell=True, check=False)
                    if res.returncode != 0:
                        images[image] = False
                        next
                    cmd = 'docker push {}:{}'.format(repo, os)
                    print(' {}'.format(cmd))
                    res = subprocess.run(cmd, shell=True, check=False)
                    if res.returncode != 0:
                        images[image] = False
                        next
            else:
                if latest_dict[ver_maj] == image:
                    # major.minor-os
                    cmd = 'docker tag {}:{}-{} {}:{}-{}'.format(repo, image, os, repo, ver_maj, os)
                    print(' {}'.format(cmd))
                    res = subprocess.run(cmd, shell=True, check=False)
                    if res.returncode != 0:
                        images[image] = False
                        next
                    cmd = 'docker push {}:{}-{}'.format(repo, ver_maj, os)
                    print(' {}'.format(cmd))
                    res = subprocess.run(cmd, shell=True, check=False)
                    if res.returncode != 0:
                        images[image] = False
                        next

    return images



parser = argparse.ArgumentParser(description='Build and push Ansible docker images')

parser.add_argument('-o', '--os', default='slim',
    help="name of the distro to build, e.g. slim, alpine", required=True)
parser.add_argument('--latest', '-l', action="store_true",
    help="latest flag specifies whether default docker tags should be applied (latest)")
parser.add_argument('--docker-name', '-d', default='sbocinec/ansible', type=str,
    help="Docker repository name, i.e. sbocinec/ansible")
parser.add_argument('--ansible-name', '-a', default='ansible/ansible', type=str,
    help="Ansible GtiHub repository name, i.e. ansible/ansible")

args = parser.parse_args()

docker_hub_auth_token = docker_hub_auth(args.docker_name)
docker_image_tags = docker_hub_get_image_tags(args.docker_name, docker_hub_auth_token)
docker_image_tags = filter_distro_tags(docker_image_tags, args.os)
ansible_release_tags = github_get_project_tags(args.ansible_name)

# print(docker_image_tags)
# print(ansible_release_tags)

latest_versions = find_majmin_tags(latest_versions, docker_image_tags)
print(latest_versions)
check_version(ansible_release_tags, docker_image_tags)
build_versions = build_images(build_versions, args.docker_name, args.os)
build_versions = test_images(build_versions, args.docker_name, args.os)
latest_versions = find_majmin_tags(latest_versions, [key for key in build_versions if build_versions[key]])
latest_version = find_latest(list(latest_versions.values()))

build_versions = tag_images(build_versions, args.docker_name, args.os, args.latest, latest_versions, latest_version)

failed_builds = [key for key in build_versions if not build_versions[key]]
if len(failed_builds) > 0:
    print('Failed to build docker images for following ansible versions: {}'.format(failed_builds))
    sys.exit(1)
