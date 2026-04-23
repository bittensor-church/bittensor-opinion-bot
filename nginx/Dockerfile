FROM ghcr.io/reef-technologies/nginx-rt:v1.2.2
COPY nginx/stream.conf /etc/nginx/stream.conf
RUN grep -q "include /etc/nginx/stream.conf;" /etc/nginx/nginx.conf || echo "include /etc/nginx/stream.conf;" >> /etc/nginx/nginx.conf
