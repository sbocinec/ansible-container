FROM python:3.9.3-slim as build

ARG ANSIBLE_VERSION

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libffi-dev libssl-dev
RUN pip3 install --upgrade pip
RUN pip install --install-option="--prefix=/install" ansible==${ANSIBLE_VERSION}

FROM python:3.9.3-slim
LABEL maintainer="sbocinec@juniq.eu"

RUN apt-get update && \
    apt-get install -y --no-install-recommends openssh-client rsync && \
    apt-get clean  && \
    rm -rf /var/lib/apt/lists/*

COPY --from=build /install /usr/local

ENV USER ansible
ENV UID 9999
ENV GID 9999

RUN groupadd -g $GID $USER && \
    useradd -u $UID -g $GID -m $USER

USER $USER
WORKDIR /ansible

CMD [ "ansible-playbook", "--version" ]
