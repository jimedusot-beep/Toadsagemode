# Trusted, opt-in local image; never build a Dockerfile proposed by an AI.
# Version is deliberate; reevaluate release security and digest on updates.
FROM mcr.microsoft.com/playwright:v1.65.1-noble
RUN mkdir -p /opt/toad-web && npm install --prefix /opt/toad-web --no-audit --no-fund --ignore-scripts --omit=dev playwright@1.65.1
COPY runner.cjs /opt/toad-web/runner.cjs
RUN chmod 0555 /opt/toad-web/runner.cjs && chmod -R a+rX /opt/toad-web
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV HOME=/tmp
USER 65532:65532
WORKDIR /work
ENTRYPOINT ["/usr/bin/node", "/opt/toad-web/runner.cjs"]
