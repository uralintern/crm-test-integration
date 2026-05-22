FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json .npmrc ./
RUN npm ci

ARG VITE_API_BASE=
ARG VITE_USE_MOCK=false
ARG VITE_TESTING_URL=
ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_USE_MOCK=$VITE_USE_MOCK
ENV VITE_TESTING_URL=$VITE_TESTING_URL

COPY . .
RUN npm run build

FROM caddy:2.8-alpine

COPY --from=build /app/dist /srv/front
COPY Caddyfile /etc/caddy/Caddyfile
