FROM docker

FROM python:3

WORKDIR /opt/minanet

COPY minanet_app/* ./
COPY requirements.txt .

RUN apt-get update && apt-get -qq -y install cron at less vim curl
RUN pip3 install -r requirements.txt
RUN chmod +x ./entrypoint

ENTRYPOINT ["/opt/minanet/entrypoint"]