# Node.js service image (dev deps included so `npm start`/`npm test` run via tsx).
FROM node:20-bookworm-slim
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
ENV NODE_ENV=production
CMD ["npm", "start"]
