# Domain Setup Guide for news-lens.info

This guide walks you through setting up your domain `news-lens.info` with SSL/HTTPS.

## Step 1: Configure DNS at Strato.de

1. **Login to Strato Dashboard**: https://www.strato.de/apps/CustomerService
2. Navigate to **Domain Management** → **news-lens.info** → **DNS Settings**
3. Add these DNS records:

```
Type: A
Name: @
Value: 34.40.106.96
TTL: 3600

Type: A  
Name: www
Value: 34.40.106.96
TTL: 3600
```

4. **Save changes** and wait for DNS propagation (15 min - 2 hours)
5. **Verify DNS** with: `nslookup news-lens.info` or https://dnschecker.org

---

## Step 2: Choose Your Reverse Proxy

You have **two options** for SSL setup:

### Option A: **Caddy** (Recommended - Easier)

✅ **Pros:**
- Automatic SSL certificate generation
- Auto-renewal built-in
- Simpler configuration
- Zero manual certificate management

**Setup:**
```bash
./setup-caddy.sh
```

That's it! Caddy handles everything automatically.

---

### Option B: **Nginx** (More Control)

✅ **Pros:**
- More widely used
- More configuration options
- Battle-tested at scale

**Setup:**

1. **Edit setup-ssl.sh** and change the email:
```bash
nano setup-ssl.sh
# Change: EMAIL="your-email@example.com"
# To: EMAIL="your-real-email@example.com"
```

2. **Run the setup script:**
```bash
./setup-ssl.sh
```

3. **Verify certificate was created:**
```bash
docker-compose -f docker-compose.nginx.yml run --rm certbot certificates
```

4. **Restart Nginx:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.nginx.yml restart nginx
```

---

## Step 3: Update Application Environment

After DNS is working, update your `.env` file:

```bash
# Add/Update these lines in .env
CORS_ORIGINS=https://news-lens.info,https://www.news-lens.info,http://news-lens.info,http://www.news-lens.info
NEXT_PUBLIC_API_URL=https://news-lens.info
NEXT_PUBLIC_API_MODE=proxy
```

Then restart services:
```bash
# With Caddy:
docker-compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.caddy.yml down
docker-compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.caddy.yml up -d

# With Nginx:
docker-compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.nginx.yml down
docker-compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.nginx.yml up -d
```

---

## Step 4: Configure Firewall

Ensure ports are open on your server:

```bash
# Ubuntu/Debian (ufw):
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status

# Or check GCP Firewall Rules in Cloud Console
```

---

## Step 5: Test Your Setup

1. **Check DNS resolution:**
```bash
nslookup news-lens.info
# Should return: 34.40.106.96
```

2. **Test HTTP redirect:**
```bash
curl -I http://news-lens.info
# Should redirect to https://
```

3. **Test HTTPS:**
```bash
curl -I https://news-lens.info
# Should return 200 OK
```

4. **Test in browser:**
- Frontend: https://news-lens.info
- API: https://news-lens.info/api/health
- Airflow: https://news-lens.info/airflow

---

## Service URLs After Setup

| Service | URL |
|---|---|
| **Main Website** | https://news-lens.info |
| **API** | https://news-lens.info/api/* |
| **Airflow UI** | https://news-lens.info/airflow |
| **Health Check** | https://news-lens.info/health |

---

## Troubleshooting

### DNS not resolving
```bash
# Check DNS propagation
nslookup news-lens.info
dig news-lens.info

# May take up to 48 hours, usually < 2 hours
```

### SSL certificate failed (Nginx only)
```bash
# Check Nginx logs
docker logs news-lens-nginx

# Check Certbot logs
docker-compose -f docker-compose.nginx.yml run --rm certbot certificates

# Make sure DNS is pointing to server first!
```

### Caddy certificate failed
```bash
# Check Caddy logs
docker logs news-lens-caddy -f

# Caddy shows detailed SSL errors in logs
```

### Service not accessible
```bash
# Check if all services are running
docker ps

# Check specific service logs
docker logs news-lens-frontend
docker logs news-lens-backend
docker logs news-lens-caddy  # or nginx

# Check if ports are open
sudo netstat -tulpn | grep -E ':(80|443)'
```

### CORS errors in browser
Make sure `.env` has correct CORS_ORIGINS and restart backend:
```bash
docker-compose -f docker-compose.prod.yml restart backend
```

---

## Certificate Renewal

### Caddy
- ✅ **Automatic** - no action needed

### Nginx + Certbot
- Auto-renewal runs every 12 hours via the certbot container
- Manual renewal: `docker-compose -f docker-compose.nginx.yml run --rm certbot renew`
- Check expiry: `docker-compose -f docker-compose.nginx.yml run --rm certbot certificates`

---

## Production Checklist

- [ ] DNS A records configured at Strato
- [ ] DNS propagated and verified
- [ ] Reverse proxy deployed (Caddy or Nginx)
- [ ] SSL certificate obtained
- [ ] Firewall ports 80 and 443 open
- [ ] `.env` updated with domain URLs
- [ ] All services restarted
- [ ] HTTPS working in browser
- [ ] API endpoints accessible
- [ ] Changed Airflow password from default

---

## Architecture Diagram

```
Internet
   ↓
Strato DNS (news-lens.info) → 34.40.106.96
   ↓
[Caddy/Nginx] :80, :443
   ↓
   ├─→ Frontend (Next.js) :3000  → Browser
   ├─→ Backend (FastAPI) :8000   → /api/*
   └─→ Airflow :8080             → /airflow/*
```

---

## Need Help?

Run these diagnostic commands:
```bash
# Check all containers
docker ps

# Check reverse proxy logs
docker logs news-lens-caddy -f    # or news-lens-nginx

# Test internal networking
docker exec news-lens-caddy wget -O- http://frontend:3000
docker exec news-lens-caddy wget -O- http://backend:8000/health
```
