#!/bin/bash

echo "=== Testing Login Flow ==="

# 1. Register a new test user
echo -e "\n1. Registering user..."
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser456","password":"test123"}' \
  -c cookies.txt

# 2. Login
echo -e "\n\n2. Logging in..."
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser456","password":"test123"}' \
  -c cookies.txt -b cookies.txt

# 3. Check auth status with cookies
echo -e "\n\n3. Checking auth status..."
curl http://localhost:5000/api/check-auth \
  -b cookies.txt

# 4. Try to access home page
echo -e "\n\n4. Accessing home page..."
curl -v http://localhost:5000/ \
  -b cookies.txt 2>&1 | grep -E "(HTTP|Location| authenticated)"

echo -e "\n\n=== Test Complete ==="
