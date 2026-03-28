#!/bin/bash
# Setup SSL certificate for news-lens.info with Nginx + Certbot

set -e

DOMAIN="news-lens.info"
EMAIL="your-email@example.com"  # CHANGE THIS!

echo "=== News Lens SSL Setup ==="
echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo ""

# Check if email is changed
if [ "$EMAIL" = "your-email@example.com" ]; then
    echo "ERROR: Please edit this script and set your real email address!"
    exit 1
fi

# Create directories
echo "Creating directories..."
mkdir -p certbot/conf certbot/www nginx/logs

# Start nginx with temporary config for HTTP-01 challenge
echo "Starting Nginx for certificate generation..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.nginx.yml up -d nginx

# Wait for nginx to be ready
echo "Waiting for Nginx to start..."
sleep 5

# Request certificate
echo "Requesting SSL certificate from Let's Encrypt..."
docker-compose -f docker-compose.nginx.yml run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN" \
    -d "www.$DOMAIN"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SSL certificate generated successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Restart Nginx to use the new certificate:"
    echo "   docker-compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.nginx.yml restart nginx"
    echo ""
    echo "2. Test your site at: https://news-lens.info"
else
    echo ""
    echo "❌ Certificate generation failed!"
    echo "Make sure:"
    echo "1. DNS is pointing to this server (34.40.106.96)"
    echo "2. Ports 80 and 443 are open in firewall"
    echo "3. Domain name is correct"
fi
