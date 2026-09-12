# Local compose (bind-mount + next dev). Production images use the last
# stage (`production`) so a mistaken `docker build` does not ship `next dev`.
FROM node:20-alpine AS base

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

FROM base AS development
ENV NODE_ENV=development
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM base AS production
ENV NODE_ENV=production
ARG NEXT_PUBLIC_USE_API_PROXY=true
ENV NEXT_PUBLIC_USE_API_PROXY=$NEXT_PUBLIC_USE_API_PROXY
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
