import requests
import json

# Test registration
print("Testing registration...")
register_data = {
    "username": "testuser123",
    "password": "test123"
}
reg_response = requests.post('http://localhost:5000/api/register', json=register_data)
print(f"Register response: {reg_response.status_code}")
print(f"Register data: {reg_response.json()}")

# Test login
print("\nTesting login...")
login_response = requests.post('http://localhost:5000/api/login', json=register_data)
print(f"Login response: {reg_response.status_code}")
print(f"Login data: {login_response.json()}")

# Get cookies
cookies = login_response.cookies
print(f"\nCookies received: {cookies}")

# Test check-auth with cookies
print("\nTesting check-auth...")
auth_response = requests.get('http://localhost:5000/api/check-auth', cookies=cookies)
print(f"Auth response: {auth_response.json()}")
