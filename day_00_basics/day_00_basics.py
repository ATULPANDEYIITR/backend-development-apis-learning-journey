# ============================================================
# DAY 00: BACKEND FUNDAMENTALS
# ============================================================

print("DAY 01 - BACKEND FUNDAMENTALS")


# ============================================================
# 1. WHAT IS BACKEND DEVELOPMENT?
# ============================================================

print("\n1. WHAT IS BACKEND DEVELOPMENT?")

print("Backend development focuses on the server-side")
print("logic, data, APIs, authentication, and processing")
print("that power applications.")


# ============================================================
# 2. FRONTEND VS BACKEND
# ============================================================

print("\n2. FRONTEND VS BACKEND")

frontend = "What the user sees and interacts with"
backend = "What processes requests and manages application logic"

print("Frontend:", frontend)
print("Backend:", backend)


# ============================================================
# 3. CLIENT AND SERVER
# ============================================================

print("\n3. CLIENT AND SERVER")

client = "Web Browser"
server = "Backend Server"

print("Client:", client)
print("Server:", server)

print("\nBasic communication:")
print("Client -> Request -> Server")
print("Client <- Response <- Server")


# ============================================================
# 4. REQUEST
# ============================================================

print("\n4. REQUEST")

request = {
    "method": "GET",
    "path": "/users",
    "status": "Received"
}

print("Request Method:", request["method"])
print("Request Path:", request["path"])
print("Request Status:", request["status"])


# ============================================================
# 5. RESPONSE
# ============================================================

print("\n5. RESPONSE")

response = {
    "status_code": 200,
    "message": "Request successful",
    "data": ["User 1", "User 2", "User 3"]
}

print("Status Code:", response["status_code"])
print("Message:", response["message"])
print("Data:", response["data"])


# ============================================================
# 6. HTTP METHODS
# ============================================================

print("\n6. COMMON HTTP METHODS")

http_methods = {
    "GET": "Retrieve data",
    "POST": "Create data",
    "PUT": "Update data",
    "PATCH": "Partially update data",
    "DELETE": "Delete data"
}

for method, purpose in http_methods.items():
    print(method, "->", purpose)


# ============================================================
# 7. STATUS CODES
# ============================================================

print("\n7. COMMON HTTP STATUS CODES")

status_codes = {
    200: "OK",
    201: "Created",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    500: "Internal Server Error"
}

for code, meaning in status_codes.items():
    print(code, "->", meaning)


# ============================================================
# 8. BACKEND LOGIC
# ============================================================

print("\n8. BASIC BACKEND LOGIC")

username = "Atul"
is_authenticated = True

if is_authenticated:
    message = "Welcome " + username
else:
    message = "Authentication required"

print(message)


# ============================================================
# 9. SIMPLE API-LIKE FUNCTION
# ============================================================

print("\n9. SIMPLE API-LIKE FUNCTION")


def get_user(user_id):
    users = {
        1: "Atul",
        2: "Rahul",
        3: "Priya"
    }

    return users.get(user_id, "User not found")


print("User 1:", get_user(1))
print("User 2:", get_user(2))
print("User 99:", get_user(99))


# ============================================================
# 10. DATA PROCESSING
# ============================================================

print("\n10. BASIC DATA PROCESSING")

users = [
    {"id": 1, "name": "Atul"},
    {"id": 2, "name": "Rahul"},
    {"id": 3, "name": "Priya"}
]

for user in users:
    print("ID:", user["id"], "| Name:", user["name"])


# ============================================================
# 11. BACKEND FLOW
# ============================================================

print("\n11. BASIC BACKEND FLOW")

print("""
1. Client sends a request
2. Server receives the request
3. Backend processes the request
4. Backend may interact with a database
5. Backend prepares a response
6. Server sends the response to the client
""")


# ============================================================
# SUMMARY
# ============================================================

print("=" * 60)
print("DAY 01 COMPLETED")
print("=" * 60)

print("""
Today you learned:

1. What backend development is
2. Frontend vs backend
3. Client and server
4. Requests and responses
5. HTTP methods
6. HTTP status codes
7. Basic backend logic
8. Functions
9. Basic API concepts
10. Data processing
11. Basic backend request flow
""")

