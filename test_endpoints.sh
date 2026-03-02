# Test available endpoints
for endpoint in \
  "/" \
  "/health" \
  "/ready" \
  "/api/v1/info" \
  "/api/v1/jobs" \
  "/auth/register" \
  "/api/v1/auth/register" \
  "/register" \
  "/login"; do
  echo "Testing: http://localhost:8001$endpoint"
  curl -s "http://localhost:8001$endpoint" || echo "Failed"
  echo ""
done
