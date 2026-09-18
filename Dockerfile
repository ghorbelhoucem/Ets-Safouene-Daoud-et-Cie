FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html config.js client.js inventory.js keyboardScanner.js machine.js renderer.js store.js /usr/share/nginx/html/
EXPOSE 80
