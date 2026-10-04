# BRouter (https://github.com/abrensch/brouter, MIT licence): routing along OpenStreetMap
# paths for planned routes. The path data (segments) is not part of the image; it lives
# under DATA_DIR/brouter/segments and is fetched with deploy/brouter-segments.sh.
FROM eclipse-temurin:21-jre-alpine AS fetch
ARG BROUTER_VERSION=1.7.10
ARG BROUTER_SHA256=023fec3ba997758e8cd7ab9e1bae52e962af3f00b57683e3de86b84ffad01532
RUN apk add --no-cache curl unzip
WORKDIR /fetch
RUN curl -fsSL -o brouter.zip \
      "https://github.com/abrensch/brouter/releases/download/v${BROUTER_VERSION}/brouter-${BROUTER_VERSION}.zip" \
    && echo "${BROUTER_SHA256}  brouter.zip" | sha256sum -c - \
    && unzip -q brouter.zip \
    && mkdir /brouter \
    && mv "brouter-${BROUTER_VERSION}/brouter-${BROUTER_VERSION}-all.jar" /brouter/brouter.jar \
    && mv "brouter-${BROUTER_VERSION}/profiles2" /brouter/profiles

FROM eclipse-temurin:21-jre-alpine
COPY --from=fetch /brouter /brouter
# The profile of hiker next to the ones BRouter ships (lookups.dat must be in the same folder).
COPY profiles/ /brouter/profiles/
ENV JAVA_OPTS="-Xmx384m -Xms64m" \
    BROUTER_THREADS=2 \
    BROUTER_MAX_SECONDS=25
EXPOSE 17777
USER 1000:1000
# RouteServer <segments> <profiles> <uploaded profiles> <port> <threads>
CMD ["sh", "-c", "exec java $JAVA_OPTS -DmaxRunningTime=$BROUTER_MAX_SECONDS -cp /brouter/brouter.jar btools.server.RouteServer /segments /brouter/profiles /tmp/profiles 17777 $BROUTER_THREADS"]
