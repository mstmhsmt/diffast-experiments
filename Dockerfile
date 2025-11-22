FROM mhashimoto/rrj:devel

LABEL maintainer="mstmhsmt"

WORKDIR /root

COPY README.md /root/
COPY refactoring /root/refactoring
COPY direct /root/direct

RUN set -x && \
    cd /root && \
    apt-get update && \
    env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
            gradle \
            openjdk-17-jdk \
            python3-pandas \
            python3-seaborn

ENV LC_ALL=en_US.UTF8

RUN set -x && \
    cd /root/direct/GumTreeDiff/gumtree && \
    patch -p1 < ../gumtree-unicode-fix.patch && \
    ./gradlew build && \
    cp dist/build/distributions/gumtree-*-SNAPSHOT.zip .. && \
    cd .. && \
    unzip gumtree-*-SNAPSHOT.zip

RUN set -x && \
    mkdir /root/refactoring/GumTree/libs && \
    cd /root/refactoring/GumTree/libs && \
    ln -s ../../../direct/GumTreeDiff/gumtree-*-SNAPSHOT/lib/gumtree.jar .

# Cleanup

RUN set -x && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]
