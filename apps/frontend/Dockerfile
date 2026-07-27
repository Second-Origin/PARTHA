# Development image for the PARTHA frontend.
# Runs the Vite dev server so `docker compose up` brings up the whole stack
# (api + postgres + redis + frontend) in one command. Hot reload works because
# the compose service mounts the source directory.
FROM node:20-alpine

WORKDIR /app

# Install dependencies first for better layer caching.
COPY package.json package-lock.json ./
RUN npm install

# Vite must bind to 0.0.0.0 inside the container so the published port is
# reachable from the host. The frontend reaches the backend by its compose
# service name (http://api:8000), not localhost.
ENV VITE_API_URL=http://api:8000
EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
