ARG PAPERCLIP_IMAGE_TAG=latest
FROM ghcr.io/paperclipai/paperclip:${PAPERCLIP_IMAGE_TAG}
USER root
COPY patch-claim-crash.mjs /tmp/patch-claim-crash.mjs
RUN node /tmp/patch-claim-crash.mjs && rm /tmp/patch-claim-crash.mjs
