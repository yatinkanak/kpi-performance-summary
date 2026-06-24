FROM node:26-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173
# Dev server is sufficient for the take-home; for production build + serve via nginx.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
