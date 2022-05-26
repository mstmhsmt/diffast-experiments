FROM mhashimoto/rrj

MAINTAINER mstmhsmt

WORKDIR /root

COPY README.md /root/
COPY refactoring /root/refactoring
COPY direct /root/direct

RUN set -x && \
    cd /root && \
    apt-get update && \
    env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
            gradle \
            openjdk-11-jdk \
            python3-pandas \
            python3-seaborn

ENV LC_ALL=en_US.UTF8

RUN set -x && \
    cd /root/direct/GumTreeDiff/gumtree && \
    patch -p1 < ../gumtree-unicode-fix.patch && \
    ./gradlew build && \
    cp dist/build/distributions/gumtree-3.1.0-SNAPSHOT.zip .. && \
    cd .. && \
    unzip gumtree-3.1.0-SNAPSHOT.zip

RUN set -x && \
    cd /root/refactoring/GumTree/libs && \
    ln -s ../../../direct/GumTreeDiff/gumtree-3.1.0-SNAPSHOT/lib/gumtree.jar .

# Cleanup

RUN set -x && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]
