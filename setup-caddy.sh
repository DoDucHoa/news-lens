#!/bin/bash
# Setup SSL certificate for news-lens.info with Caddy

set -e

DOMAIN="news-lens.info"

echo "=== News Lens SSL Setup with Caddy ==="
echo "Domain: $DOMAIN"
echo ""

# Create directories
echo "Creating directories..."
mkdir -p caddy/data caddy/config caddy/logs

# Update environment variables
echo "Updating environment variables..."
cat > .env.domain << 'EOF'
# Domain Configuration for news-lens.info
CORS_ORIGINS=https://news-lens.info,https://www.news-lens.info,http://news-lens.info,http://www.news-lens.info
NEXT_PUBLIC_API_URL=https://news-lens.info
NEXT_PUBLIC_API_MODE=proxy
EOF

echo ""
echo "Environment configuration created in .env.domain"
echo "Merge this with your existing .env file"
echo ""

# Start services
echo "Starting services with Caddy reverse proxy..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.caddy.yml up -d

echo ""
echo "✅ Caddy is starting!"
echo ""
echo "Caddy will automatically:"
echo "  - Obtain SSL certificate from Let's Encrypt"
echo "  - Configure HTTPS"
echo "  - Set up auto-renewal"
echo ""
echo "Check logs: docker logs news-lens-caddy -f"
echo "Your site will be available at: https://news-lens.info"
echo ""
echo "⏱️  First SSL cert may take 30-60 seconds to generate"
