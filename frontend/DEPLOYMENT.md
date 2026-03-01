# Website Deployment Guide

## Overview
This guide covers deployment of the Quantum-Safe Secure Optimization Platform website.

## Prerequisites
- Domain name configured (e.g., quantum-safe-optimization.com)
- SSL certificate (Let's Encrypt recommended)
- Docker and Docker Compose installed
- 4GB RAM minimum for full deployment

## Quick Start

### 1. Environment Configuration
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 2. Build and Deploy
```bash
docker-compose build
docker-compose up -d
```

### 3. Access the Application
- Website: `http://localhost:80` (or your domain)
- API: `http://localhost:80/api/`
- Health Check: `http://localhost:80/health`

## Deployment Options

### Option A: Local Development
```bash
cd frontend
python -m http.server 8080
# Access at http://localhost:8080
```

### Option B: Docker Deployment (Recommended)
```bash
docker-compose up -d
```

### Option C: Production with Nginx
```bash
# Copy frontend/nginx.conf to /etc/nginx/sites-available/quantum-safe
sudo ln -s /etc/nginx/sites-available/quantum-safe /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Option D: Cloud Deployment (AWS/GCP/Azure)
See `docs/deployment/cloud.md` for cloud-specific instructions.

## File Structure

```
frontend/
├── index.html              # Main landing page
├── dashboard.html          # Application dashboard
├── robots.txt              # Search engine rules
├── sitemap.xml             # URL index for SEO
├── favicon.ico             # Browser icon
├── manifest.json           # PWA configuration
├── nginx.conf              # Nginx server configuration
├── css/                    # Stylesheets
├── js/                     # JavaScript modules
└── assets/
    ├── images/             # Images and logos
    │   └── logo-512.svg
    └── icons/              # App icons
        ├── app-icon-512.svg
        └── maskable-icon-192.svg
```

## SSL/TLS Configuration

### Let's Encrypt (Free)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d quantum-safe-optimization.com
```

### Manual Certificate
Place your certificates in:
```
/etc/ssl/certs/quantum-safe-cert.pem
/etc/ssl/private/quantum-safe-key.pem
```

Update `nginx.conf` to include SSL paths.

## Performance Optimization

### Static Asset Caching
- Assets cached for 1 year (immutable)
- CSS/JS cached for 1 year
- HTML cached with ETag

### Gzip Compression
Enabled in `nginx.conf` for:
- Text files: .txt, .css, .json, .xml
- Scripts: .js, .svg
- Fonts: .woff, .woff2, .ttf

### CDN Integration (Optional)
```nginx
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
    proxy_pass https://your-cdn.com;
    proxy_cache_valid 200 365d;
}
```

## Security Configuration

### Headers (Already Configured)
- X-Frame-Options: SAMEORIGIN
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: no-referrer-when-downgrade

### Additional Recommendations
```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

## PWA Configuration

The site is PWA-ready with:
- Offline capability
- Installable shortcuts
- Responsive design
- App icons

Test PWA:
1. Open DevTools → Application
2. Check Manifest, Service Workers
3. Lighthouse → PWA audit

## Monitoring

### Health Check
```bash
curl http://localhost/health
# Response: healthy
```

### Logs
```bash
# Application logs
docker-compose logs -f web

# Nginx logs
docker-compose logs -f nginx

# Backend logs
docker-compose logs -f backend
```

### Metrics (Prometheus)
Configure in `backend/observability/metrics.py`

## Troubleshooting

### Website Not Loading
```bash
docker-compose ps
docker-compose logs web
```

### API 404 Errors
Check api proxy configuration in `nginx.conf`

### Assets Not Found
Verify directory permissions:
```bash
ls -la frontend/assets/
```

### PWA Installation Failed
Validate `manifest.json`:
```bash
python -m json.tool frontend/manifest.json
```

## Maintenance

### Update Content
1. Edit HTML files in `frontend/`
2. Restart containers: `docker-compose restart web`
3. Clear browser cache

### Update Code
```bash
git pull
docker-compose build
docker-compose up -d
```

### Backup
```bash
docker-compose exec backend python -m qsop.infrastructure.persistence.backup
```

## SEO Optimization

- Sitemap submitted: `https://your-domain.com/sitemap.xml`
- Robots.txt configured
- Meta tags in HTML
- Semantic HTML structure

Submit to Google Search Console:
1. Verify domain ownership
2. Submit sitemap
3. Request indexing

## Contact

For deployment issues:
- GitHub Issues: https://github.com/anomalyco/opencode/issues
- Documentation: https://docs.quantum-safe-optimization.com
