# JarlPM Auth Testing Playbook

## Step 1: Create Test User & Session
```bash
mongosh --eval "
use('jarlpm');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  picture: 'https://via.placeholder.com/150',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
db.subscriptions.insertOne({
  subscription_id: 'sub_test_' + Date.now(),
  user_id: userId,
  status: 'active',
  created_at: new Date()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
"
```

## Step 2: Test Backend API
```bash
# Test auth endpoint
curl -X GET "http://localhost:8001/api/auth/me" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"

# Test subscription status
curl -X GET "http://localhost:8001/api/subscription/status" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"

# Test create epic
curl -X POST "http://localhost:8001/api/epics" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -d '{"title": "Test Epic"}'

# Test list epics
curl -X GET "http://localhost:8001/api/epics" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

## Step 3: Browser Testing
```python
# Set cookie and navigate
await page.context.add_cookies([{
    "name": "session_token",
    "value": "YOUR_SESSION_TOKEN",
    "domain": "localhost",
    "path": "/",
    "httpOnly": True,
    "secure": False,
    "sameSite": "Lax"
}])
await page.goto("http://localhost:3000/dashboard")
```

## Quick Debug
```bash
# Check data format
mongosh --eval "
use('jarlpm');
db.users.find().limit(2).pretty();
db.user_sessions.find().limit(2).pretty();
db.subscriptions.find().limit(2).pretty();
"

# Clean test data
mongosh --eval "
use('jarlpm');
db.users.deleteMany({email: /test\.user\./});
db.user_sessions.deleteMany({session_token: /test_session/});
db.subscriptions.deleteMany({subscription_id: /sub_test/});
"
```

## Checklist
- [ ] User document has user_id field (custom UUID, MongoDB's _id is separate)
- [ ] Session user_id matches user's user_id exactly
- [ ] All queries use `{"_id": 0}` projection to exclude MongoDB's _id
- [ ] Backend queries use user_id (not _id or id)
- [ ] API returns user data with user_id field (not 401/404)
- [ ] Browser loads dashboard (not login page)

## Success Indicators
✅ /api/auth/me returns user data
✅ Dashboard loads without redirect
✅ CRUD operations work

## Failure Indicators
❌ "User not found" errors
❌ 401 Unauthorized responses
❌ Redirect to login page
