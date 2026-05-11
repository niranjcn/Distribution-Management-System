FROM node:20-alpine

WORKDIR /app

ARG VITE_API_URL=http://backend:8080/api
ENV VITE_API_URL=$VITE_API_URL

COPY package*.json /app/
RUN npm ci

COPY . /app
RUN npm run build

RUN mkdir -p /app/node_modules/.vite /app/node_modules/.vite-temp \
	&& chown -R node:node /app

EXPOSE 5173

USER node

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "5173"]
