FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html
RUN ls -la /usr/share/nginx/html/
