FROM ghcr.io/predohenr/miningframework:mergetools as mining_framework

FROM eclipse-temurin:17-jre-focal

RUN apt-get update && \
    apt-get install -y git procps gosu && \
    apt-get clean

WORKDIR /usr/src/miningframework

COPY --from=mining_framework /usr/local/framework /usr/local/framework

RUN chmod +x /usr/local/framework/bin/miningframework
ENV PATH="/usr/local/framework/bin:${PATH}"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]