FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_API_URL=http://backend:8080/api
ENV VITE_API_URL=$VITE_API_URL

COPY package*.json /app/
RUN npm ci

COPY . /app
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Serve the site as the unprivileged 'nginx' user (uid/gid 101 in the official
# alpine image) instead of root. The static assets are read-only; the writable
# runtime dirs (/var/run, /var/cache/nginx, /var/log/nginx) are tmpfs mounts
# owned by this user in docker-compose.yml, so the container does not need any
# privilege elevation. Binding the exposed port needs no privileges inside the
# container network namespace.
USER nginx

EXPOSE 80

ENTRYPOINT ["nginx", "-g", "daemon off;"]
