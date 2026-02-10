# Animal API Service - Deployment Guide

This guide covers deploying the Animal API service to a VPS (Ubuntu-based) using Docker with SSL certificate support via Let's Encrypt.

## Prerequisites

- Ubuntu VPS (20.04+ or 22.04+ recommended)
- SSH access to your VPS
- **Domain name with subdomain** (e.g., api.yourdomain.com)
- Root or sudo access

## Quick Deployment Steps

### 1. Connect to Your VPS

```bash
ssh username@your-vps-ip
```

### 2. Update System

```bash
sudo apt update
sudo apt upgrade -y
```

### 3. Install Required Software

```bash
# Install Docker and Docker Compose
sudo apt install docker.io docker-compose git -y

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to docker group (to run docker without sudo)
sudo usermod -aG docker $USER

# Install Nginx (reverse proxy)
sudo apt install nginx -y

# Install Certbot for SSL
sudo apt install certbot python3-certbot-nginx -y

# Log out and back in for docker group to take effect
exit
# Then reconnect via SSH
```

### 4. Transfer Your Code to VPS

#### Option A: Using Git (Recommended)

```bash
cd /opt
sudo git clone https://github.com/yourusername/animals-service.git
cd animals-service
```

#### Option B: Using SCP (from your local machine)

```bash
# On your local machine
tar -czf animals-service.tar.gz animals-service/
scp animals-service.tar.gz username@your-vps-ip:/opt/

# On your VPS
cd /opt
sudo tar -xzf animals-service.tar.gz
cd animals-service
```

### 5. Create Docker Configuration Files

#### Create Dockerfile

```bash
cd /opt/animals-service
sudo nano Dockerfile
```

Paste the following:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run application with gunicorn
CMD ["gunicorn", "app.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

Save and exit (Ctrl+X, then Y, then Enter).

#### Create docker-compose.yml

```bash
sudo nano docker-compose.yml
```

Paste the following:

```yaml
version: "3.8"

services:
  animals-service:
    build: .
    container_name: animals-service
    restart: always
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./static:/app/static
      - ./data:/app/data
    networks:
      - animal-network

networks:
  animal-network:
    driver: bridge
```

Save and exit.

### 6. Create Environment File

```bash
cd /opt/animals-service
sudo nano .env
```

Add the following (replace with your values):

```env
API_KEY=your-generated-api-key-here
ALLOWED_ORIGINS=https://api.yourdomain.com
RATE_LIMIT=100/minute
CACHE_TTL=3600
DEBUG=false
```

**Generate a secure API key:**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Save and exit (Ctrl+X, then Y, then Enter).

### 7. Setup DNS Record

**IMPORTANT:** Before continuing, you must configure DNS:

1. Go to your domain registrar (where you registered yourdomain.com)
2. Add an **A record**:
   - **Subdomain/Host:** `api`
   - **Points to:** Your VPS IP address (e.g., 57.129.123.33)
   - **TTL:** 300 or Auto

3. Wait 5-10 minutes for DNS propagation

**Verify DNS is working:**

```bash
# Check if DNS has propagated
nslookup api.yourdomain.com

# Or use dig
dig api.yourdomain.com
```

The result should show your VPS IP address.

### 8. Build and Run Docker Container

```bash
cd /opt/animals-service

# Build the Docker image
sudo docker-compose build

# Start the container
sudo docker-compose up -d

# Check if container is running
sudo docker-compose ps

# View logs to verify it's working
sudo docker-compose logs -f
# Press Ctrl+C to exit logs

# Test the service locally
curl http://localhost:8000/api/v1/health
```

You should see a successful response from the health endpoint.

### 9. Configure Nginx Reverse Proxy

Create Nginx configuration for your subdomain:

```bash
sudo nano /etc/nginx/sites-available/animals-service
```

Paste the following configuration:

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/animals-service/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

**Important:** Replace `api.yourdomain.com` with your actual subdomain (e.g., `api.afalco.ovh`).

Save and exit.

### 10. Enable Nginx Site

```bash
# Create symbolic link to enable the site
sudo ln -s /etc/nginx/sites-available/animals-service /etc/nginx/sites-enabled/

# Test Nginx configuration
sudo nginx -t

# If test passes, reload Nginx
sudo systemctl reload nginx
```

### 11. Setup SSL Certificate with Let's Encrypt

**Prerequisites Check:**

- DNS A record for `api.yourdomain.com` is configured
- DNS has propagated (wait 5-10 minutes after DNS setup)
- Nginx is running and accessible on port 80

```bash
# Get SSL certificate for your subdomain
sudo certbot --nginx -d api.yourdomain.com

# Follow the prompts:
# - Enter your email address
# - Agree to Terms of Service
# - Choose whether to share email with EFF
# - Select option 2 to redirect HTTP to HTTPS (recommended)
```

Certbot will automatically:

- Obtain the SSL certificate from Let's Encrypt
- Update your Nginx configuration to use HTTPS
- Configure HTTP to HTTPS redirect
- Set up automatic certificate renewal

**Verify SSL Configuration:**

After Certbot completes, your Nginx configuration will look like this:

```nginx
server {
    server_name api.yourdomain.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/animals-service/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot
}

server {
    if ($host = api.yourdomain.com) {
        return 301 https://$host$request_uri;
    } # managed by Certbot

    listen 80;
    server_name api.yourdomain.com;
    return 404; # managed by Certbot
}
```

**Test Auto-Renewal:**

```bash
# Dry run to test automatic renewal
sudo certbot renew --dry-run

# Check renewal timer status
sudo systemctl status certbot.timer
```

Certificates will automatically renew before they expire.

### 12. Configure Firewall

```bash
# Enable UFW firewall
sudo ufw enable

# Allow SSH (IMPORTANT - don't lock yourself out!)
sudo ufw allow ssh
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 'Nginx Full'

# Alternatively, allow specific ports
# sudo ufw allow 80/tcp
# sudo ufw allow 443/tcp

# Check firewall status
sudo ufw status verbose
```

### 13. Verify Deployment

```bash
# Test locally on VPS
curl http://localhost:8000/api/v1/health

# Test via subdomain (HTTP - should redirect to HTTPS)
curl http://api.yourdomain.com/api/v1/health

# Test HTTPS
curl https://api.yourdomain.com/api/v1/health

# Test with API key
curl -H "X-API-Key: your-api-key" https://api.yourdomain.com/api/v1/animals

# Test in browser
# Visit: https://api.yourdomain.com/docs
# This will show the interactive API documentation
```

**Expected Response from Health Endpoint:**

```json
{
  "status": "healthy",
  "service": "Animal API"
}
```

If you see this response, your deployment is successful! 🎉

## Service Management

### View Logs

```bash
# Docker container logs
sudo docker-compose logs -f animals-service
# Press Ctrl+C to exit

# View last 100 lines
sudo docker-compose logs --tail=100 animals-service

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### Control Docker Service

```bash
# Start containers
sudo docker-compose up -d

# Stop containers
sudo docker-compose down

# Restart containers
sudo docker-compose restart

# View running containers
sudo docker-compose ps

# View container stats (CPU, memory usage)
sudo docker stats animals-service

# Execute commands inside container
sudo docker-compose exec animals-service bash
```

### Reload Nginx

```bash
# After changing Nginx configuration
sudo nginx -t
sudo systemctl reload nginx

# Or restart Nginx
sudo systemctl restart nginx
```

## Updating the Application

### Update Code

```bash
cd /opt/animals-service

# Pull latest changes (if using Git)
sudo git pull

# Or upload new files via SCP/rsync
```

### Update Dependencies (if requirements.txt changed)

```bash
# Rebuild Docker image
cd /opt/animals-service
sudo docker-compose build

# Restart with new image
sudo docker-compose up -d
```

### Quick Restart

```bash
# If only code changed (no dependency changes)
cd /opt/animals-service
sudo docker-compose restart
```

### Full Rebuild and Restart

```bash
cd /opt/animals-service

# Stop and remove containers
sudo docker-compose down

# Rebuild images (use --no-cache to force rebuild)
sudo docker-compose build --no-cache

# Start containers
sudo docker-compose up -d

# Verify
sudo docker-compose ps
sudo docker-compose logs -f
```

## Troubleshooting

### Docker Container Won't Start

```bash
# Check container status
sudo docker-compose ps

# View container logs
sudo docker-compose logs animals-service

# Check if port 8000 is already in use
sudo lsof -i :8000
sudo netstat -tulpn | grep 8000

# Try rebuilding
sudo docker-compose down
sudo docker-compose build --no-cache
sudo docker-compose up -d
```

### Container Keeps Restarting

```bash
# View logs to see error
sudo docker-compose logs --tail=50 animals-service

# Common issues:
# - Missing .env file
# - Incorrect environment variables
# - Python dependencies not installed
# - Port already in use

# Check if .env file exists
ls -la /opt/animals-service/.env

# Verify environment variables are loaded
sudo docker-compose config
```

### Nginx Errors

```bash
# Test Nginx configuration
sudo nginx -t

# Check Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Restart Nginx
sudo systemctl restart nginx

# Check if Nginx is running
sudo systemctl status nginx
```

### SSL Certificate Issues

```bash
# List all certificates
sudo certbot certificates

# Renew certificates manually
sudo certbot renew

# Force renew (if needed)
sudo certbot renew --force-renewal

# Check certificate expiry
echo | openssl s_client -servername api.yourdomain.com -connect api.yourdomain.com:443 2>/dev/null | openssl x509 -noout -dates
```

### Can't Access API

```bash
# 1. Check if Docker container is running
sudo docker-compose ps

# 2. Check if service responds locally
curl http://localhost:8000/api/v1/health

# 3. Check if Nginx is running
sudo systemctl status nginx

# 4. Check firewall
sudo ufw status

# 5. Check DNS (if using domain)
nslookup api.yourdomain.com
dig api.yourdomain.com

# 6. Check Nginx configuration
sudo nginx -t
cat /etc/nginx/sites-enabled/animals-service

# 7. Check Docker logs
sudo docker-compose logs animals-service
```

### DNS Not Resolving

```bash
# Check DNS propagation
nslookup api.yourdomain.com
dig api.yourdomain.com

# Check from external DNS
nslookup api.yourdomain.com 8.8.8.8

# Wait up to 24 hours for full DNS propagation
# Usually takes 5-30 minutes
```

### Out of Memory

```bash
# Check Docker container memory usage
sudo docker stats animals-service

# Check system memory
free -h

# Restart container to free memory
sudo docker-compose restart

# Reduce number of workers in Dockerfile if needed
# Edit Dockerfile: --workers 2 instead of --workers 4
```

### Permission Denied Errors

```bash
# Fix ownership of application directory
sudo chown -R $USER:$USER /opt/animals-service

# Fix Docker permissions
sudo usermod -aG docker $USER
# Log out and back in

# Check file permissions
ls -la /opt/animals-service
```

## Backup Strategy

### Create Backup Script

```bash
sudo nano /opt/backup-animals-service.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/animals-service"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup data
tar -czf $BACKUP_DIR/data-$DATE.tar.gz /opt/animals-service/data

# Backup .env
cp /opt/animals-service/.env $BACKUP_DIR/env-$DATE

# Backup static files
tar -czf $BACKUP_DIR/static-$DATE.tar.gz /opt/animals-service/static

# Keep only last 7 backups
cd $BACKUP_DIR
ls -t data-*.tar.gz | tail -n +8 | xargs -r rm
ls -t env-* | tail -n +8 | xargs -r rm
ls -t static-*.tar.gz | tail -n +8 | xargs -r rm

echo "Backup completed: $DATE"
```

```bash
# Make executable
sudo chmod +x /opt/backup-animals-service.sh

# Test it
sudo /opt/backup-animals-service.sh
```

### Schedule Daily Backups

```bash
# Edit crontab
sudo crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * /opt/backup-animals-service.sh
```

## API Endpoints

Once deployed, your API will be available at `https://api.yourdomain.com`:

```
GET /api/v1/animals              - Get all animals
GET /api/v1/animals?level=5      - Filter animals by level
GET /api/v1/animals/{name}       - Get specific animal by name
GET /api/v1/animals/level/{level} - Get animals by rarity level
GET /api/v1/health               - Health check
GET /docs                        - Interactive API documentation (Swagger)
GET /redoc                       - Alternative API documentation
```

**Example Requests:**

```bash
# Health check (no API key required)
curl https://api.yourdomain.com/api/v1/health

# Get all animals (requires API key)
curl -H "X-API-Key: your-api-key" https://api.yourdomain.com/api/v1/animals

# Get animals by level
curl -H "X-API-Key: your-api-key" https://api.yourdomain.com/api/v1/animals/level/5

# Get specific animal
curl -H "X-API-Key: your-api-key" https://api.yourdomain.com/api/v1/animals/kakapo

# Filter by level using query parameter
curl -H "X-API-Key: your-api-key" "https://api.yourdomain.com/api/v1/animals?level=1"
```

**Interactive Documentation:**

Visit `https://api.yourdomain.com/docs` in your browser to see the Swagger UI with all endpoints and test them interactively.

## Security Checklist

- [ ] Strong API key generated and stored in `.env`
- [ ] `.env` file not committed to Git
- [ ] Firewall enabled and configured
- [ ] SSH key authentication enabled
- [ ] Root login disabled
- [ ] SSL certificate installed (if using domain)
- [ ] Rate limiting configured
- [ ] Regular backups scheduled
- [ ] Logs monitored regularly
- [ ] System updates applied regularly

## Performance Optimization

### Adjust Worker Processes

Edit the Dockerfile to adjust workers based on your VPS CPU cores:

```bash
sudo nano /opt/animals-service/Dockerfile
```

Change the CMD line:

```dockerfile
# For 2 CPU cores: use 5 workers (2 x CPU + 1)
CMD ["gunicorn", "app.main:app", "--workers", "5", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]

# For 4 CPU cores: use 9 workers
CMD ["gunicorn", "app.main:app", "--workers", "9", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

Then rebuild:

```bash
sudo docker-compose build
sudo docker-compose up -d
```

### Enable Nginx Caching

```bash
sudo nano /etc/nginx/sites-available/animals-service
```

Add caching configuration:

```nginx
# Add at the top, before server block
proxy_cache_path /var/cache/nginx/animals-service levels=1:2 keys_zone=animal_cache:10m max_size=100m inactive=60m;

server {
    # ... existing configuration ...

    location /api/v1/animals {
        proxy_cache animal_cache;
        proxy_cache_valid 200 5m;
        proxy_cache_key "$request_uri|$http_x_api_key";
        add_header X-Cache-Status $upstream_cache_status;

        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ... rest of configuration ...
}
```

Create cache directory:

```bash
sudo mkdir -p /var/cache/nginx/animals-service
sudo chown www-data:www-data /var/cache/nginx/animals-service
sudo nginx -t
sudo systemctl reload nginx
```

### Limit Docker Container Resources

Edit `docker-compose.yml` to add resource limits:

```bash
sudo nano /opt/animals-service/docker-compose.yml
```

```yaml
version: "3.8"

services:
  animals-service:
    build: .
    container_name: animals-service
    restart: always
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./static:/app/static
      - ./data:/app/data
    networks:
      - animal-network
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1G
        reservations:
          cpus: "0.5"
          memory: 256M

networks:
  animal-network:
    driver: bridge
```

Then restart:

```bash
sudo docker-compose up -d
```

## Monitoring

### Check System Resources

```bash
# Overall system resources
htop

# Or use top
top

# Disk usage
df -h

# Docker container resource usage
sudo docker stats animals-service

# Container details
sudo docker inspect animals-service
```

### Setup Container Health Checks

Edit `docker-compose.yml` to add health checks:

```bash
sudo nano /opt/animals-service/docker-compose.yml
```

```yaml
version: "3.8"

services:
  animals-service:
    build: .
    container_name: animals-service
    restart: always
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./static:/app/static
      - ./data:/app/data
    networks:
      - animal-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  animal-network:
    driver: bridge
```

### Setup Simple Monitoring Script

```bash
# Create monitoring script
sudo nano /opt/check-animals-service.sh
```

```bash
#!/bin/bash

# Check if container is running
if ! sudo docker-compose -f /opt/animals-service/docker-compose.yml ps | grep -q "Up"; then
    echo "$(date): Animal API container is down! Restarting..." >> /var/log/animals-service-monitor.log
    cd /opt/animals-service
    sudo docker-compose restart
    echo "$(date): Container restarted" >> /var/log/animals-service-monitor.log
fi

# Check if API responds
if ! curl -s -f http://localhost:8000/api/v1/health > /dev/null; then
    echo "$(date): API health check failed! Restarting container..." >> /var/log/animals-service-monitor.log
    cd /opt/animals-service
    sudo docker-compose restart
    echo "$(date): Container restarted due to health check failure" >> /var/log/animals-service-monitor.log
fi
```

```bash
# Make executable
sudo chmod +x /opt/check-animals-service.sh

# Test it
sudo /opt/check-animals-service.sh

# Add to crontab (check every 5 minutes)
sudo crontab -e
# Add this line:
*/5 * * * * /opt/check-animals-service.sh
```

### View Monitoring Logs

```bash
# View monitoring log
sudo tail -f /var/log/animals-service-monitor.log

# View container logs
sudo docker-compose -f /opt/animals-service/docker-compose.yml logs -f --tail=100
```

## Support

If you encounter issues:

1. **Check Docker container logs:**

   ```bash
   sudo docker-compose logs animals-service
   ```

2. **Verify container is running:**

   ```bash
   sudo docker-compose ps
   ```

3. **Check Nginx logs:**

   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

4. **Verify firewall settings:**

   ```bash
   sudo ufw status
   ```

5. **Check DNS configuration:**

   ```bash
   nslookup api.yourdomain.com
   ```

6. **Review SSL certificate:**
   ```bash
   sudo certbot certificates
   ```

## Quick Reference Commands

```bash
# Start service
cd /opt/animals-service && sudo docker-compose up -d

# Stop service
cd /opt/animals-service && sudo docker-compose down

# Restart service
cd /opt/animals-service && sudo docker-compose restart

# View logs
sudo docker-compose logs -f animals-service

# Rebuild and restart
cd /opt/animals-service && sudo docker-compose down && sudo docker-compose build && sudo docker-compose up -d

# Check status
sudo docker-compose ps

# Test API
curl https://api.yourdomain.com/api/v1/health
```

## Additional Resources

- FastAPI Documentation: https://fastapi.tiangolo.com/
- Nginx Documentation: https://nginx.org/en/docs/
- Let's Encrypt: https://letsencrypt.org/
- Ubuntu Server Guide: https://ubuntu.com/server/docs
