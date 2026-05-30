FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL=http://127.0.0.1:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV PORT=9000

RUN npm run build

EXPOSE 9000

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "9000"]
