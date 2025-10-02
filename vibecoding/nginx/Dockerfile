# Use a lightweight Nginx image
FROM nginx:alpine

# Remove the default nginx configuration file
RUN rm /etc/nginx/conf.d/default.conf

# Copy the custom nginx configuration file
COPY nginx.conf /etc/nginx/conf.d/

# Copy the frontend static files
COPY index.html /usr/share/nginx/html/
