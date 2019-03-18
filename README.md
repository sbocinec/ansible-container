# Ansible docker image builder
Automated docker image builder of all currently supported [Ansible](https://www.ansible.com/) versions. Built docker images are hosted publicly in the [sbocinec/ansible Docker HUB repository](https://cloud.docker.com/repository/docker/sbocinec/ansible). The project is currently in alpha phase of development and there are multiple build & test related things to be implemented yet. Check [CHANGELOG.md](CHANGELOG.md) for news & updates. 

There are currently 2 types of images being built:
1. **slim**: based on the [python:3.6-slim docker image](https://hub.docker.com/_/python/)
2. **alpine**: based on the [python:3.6-alpine docker image](https://hub.docker.com/_/python/)

The build pipeline currently automatically builds, tags and pushes docker images from all the Ansible versions specified in the [ANSIBLE_VERSION](docker/ANSIBLE_VERSION) file.

## Usage

### Quick start
1. Prepare complete [ansible playbook content](https://docs.ansible.com/ansible/latest/user_guide/playbooks_best_practices.html#directory-layout) including your playbooks, variables, ansible configuration file and inventory.
2. Run the container mounting the ansible playbook directory into `/ansible` path inside the container and specifying the exact ansible command: `docker run -it --rm -v ${PWD}/ansible:/ansible sbocinec:ansible ansible-playbook site.yml`. Follow the [Ansible Getting Started guide](https://docs.ansible.com/ansible/latest/user_guide/intro_getting_started.html) for full Ansible reference.

### Other examples
* **Run specific ansible version**: `docker run -it --rm -v ${PWD}/ansible:/ansible sbocinec:ansible:2.7 ansible-playbook site.yml`
* **Run ansible built on top of Alpine Linux image**: `docker run -it --rm -v ${PWD}/ansible:/ansible sbocinec:ansible:2.6-alpine ansible-playbook site.yml`


## Motivation

## Author
[Stanislav Bocinec](https://www.juniq.eu)

## License

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may find a copy of the License at [http://www.apache.org/licenses/LICENSE-2.0](http://www.apache.org/licenses/LICENSE-2.0) or in the project's [LICENSE](LICENSE) file.

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.