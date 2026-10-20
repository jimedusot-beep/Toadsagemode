# Build only this trusted context. Never build a Dockerfile from a feed.
FROM python:3.11-slim
COPY runner.py /opt/toad_lab/runner.py
RUN chmod 0555 /opt/toad_lab/runner.py
USER 65532:65532
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/python", "-I", "-B", "/opt/toad_lab/runner.py"]
