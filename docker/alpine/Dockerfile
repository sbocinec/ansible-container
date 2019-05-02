FROM python:3.6-alpine as build

ARG ANSIBLE_VERSION

RUN apk --update --no-cache add build-base libffi-dev openssl-dev && env
RUN pip3 install --upgrade pip
RUN pip install --install-option="--prefix=/install" ansible==${ANSIBLE_VERSION}

FROM python:3.6-alpine
LABEL maintainer="sbocinec@juniq.eu"

RUN apk --update --no-cache add openssh-client rsync
COPY --from=build /install /usr/local

ENV USER ansible
ENV UID 9999
ENV GID 9999

RUN addgroup -g $GID $USER && \
    adduser -u $UID -G $USER -D $USER

USER $USER
WORKDIR /ansible

CMD [ "ansible-playbook", "--version" ]
