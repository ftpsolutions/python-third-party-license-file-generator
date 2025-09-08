ARG VERSION

FROM python:${VERSION:-3.12}

WORKDIR /srv/

RUN pip install twine setuptools

COPY ./requirements.txt /srv/python-third-party-license-file-generator/requirements.txt
COPY ./pyproject.toml /srv/python-third-party-license-file-generator/pyproject.toml

RUN pip install -r /srv/python-third-party-license-file-generator/requirements.txt

COPY . /srv/python-third-party-license-file-generator

RUN pip install ./python-third-party-license-file-generator/

CMD ["/srv/python-third-party-license-file-generator/docker-entrypoint.sh"]
