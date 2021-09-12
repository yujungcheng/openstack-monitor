FROM ubuntu:focal

RUN apt-get update && apt-get install -y python3-openstackclient python3-openstacksdk 
RUN apt-get install -y mysql-client python3-pymysql


COPY ./scripts /
COPY ./start.sh /

CMD ["/start.sh"]