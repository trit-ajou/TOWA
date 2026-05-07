FROM node:20-alpine

WORKDIR /app/towa-app

COPY towa-app/package.json ./

RUN npm install --legacy-peer-deps

WORKDIR /app

COPY bitmappery ./bitmappery
COPY towa-app ./towa-app

WORKDIR /app/towa-app

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
