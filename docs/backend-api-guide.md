# Animal Quiz Academy - Backend API Guide for Flutter Client

## Overview

The backend is a FastAPI service that stores all game data (user profiles, quiz progress, coins) in **Firestore**. The Flutter app never reads from or writes to Firestore directly. All data flows through the REST API.

Authentication is handled client-side by **Firebase Authentication**. The app signs the user in via Firebase, obtains an ID token, and sends that token as a `Bearer` header on every API request. The backend verifies the token and maps it to a Firestore user document.

**Base URL:** `{SERVER}/api/v1`

---

## Authentication Flow

Every request (except health check) requires a `Bearer` token in the `Authorization` header. The token is the Firebase ID token obtained after sign-in.

```
Authorization: Bearer <firebase_id_token>
```

### Startup sequence the Flutter app must implement

```
1. Firebase sign-in (email/password, Google, Apple, etc.)
       |
       v
2. Obtain Firebase ID token  -->  store in memory, refresh before expiry
       |
       v
3. POST /api/v1/auth/register  { "username": "alice" }
   - 201 = profile created (first time)
   - 409 = profile already exists (returning user, this is fine - proceed)
       |
       v
4. GET /api/v1/auth/me  -->  load user profile (id, username, email, totalCoins, createdAt)
       |
       v
5. App is ready. Load levels, show quiz, etc.
```

### Token refresh

Firebase ID tokens expire after 1 hour. The Flutter app should use `FirebaseAuth.instance.currentUser!.getIdToken()` which auto-refreshes. Attach a fresh token to every API call. If any API call returns **401**, force-refresh the token and retry once.

---

## API Endpoints

All request/response bodies use **camelCase** JSON keys.

### 1. Register User Profile

Creates the app profile in Firestore after Firebase sign-in. Call this once after first sign-up. Safe to call again for returning users (handle the 409).

```
POST /api/v1/auth/register
```

**Request:**
```json
{
  "username": "alice"
}
```
- `username`: string, 2-30 characters, required

**Response 201:**
```json
{
  "id": "firebase-uid-abc123",
  "username": "alice",
  "email": "alice@example.com",
  "totalCoins": 0,
  "createdAt": "2025-01-15T10:30:00Z"
}
```

**Response 409 (already registered):**
```json
{
  "detail": {
    "error": {
      "code": "profile_exists",
      "message": "User profile already exists"
    }
  }
}
```

---

### 2. Get Current User

Returns the authenticated user's profile with their current coin total.

```
GET /api/v1/auth/me
```

**Response 200:**
```json
{
  "id": "firebase-uid-abc123",
  "username": "alice",
  "email": "alice@example.com",
  "totalCoins": 120,
  "createdAt": "2025-01-15T10:30:00Z"
}
```

**Response 404** (if register was never called):
```json
{
  "detail": {
    "error": {
      "code": "user_not_found",
      "message": "User profile not found. Call POST /auth/register first."
    }
  }
}
```

---

### 3. List All Levels

Returns all 6 quiz levels with their 20 animals each. Does **not** include guessed status (use the detail endpoint for that).

```
GET /api/v1/levels
```

**Response 200:**
```json
{
  "levels": [
    {
      "id": 1,
      "title": "Farm Friends",
      "emoji": "\ud83d\udc04",
      "animals": [
        {
          "id": 1,
          "name": "Dog",
          "emoji": "\ud83d\udc15",
          "imageUrl": "/static/images/dog.jpg"
        }
        // ... 19 more animals
      ]
    }
    // ... 5 more levels
  ]
}
```

---

### 4. Get Level Detail (with guessed status)

Returns a single level with per-animal `guessed` boolean. This is the endpoint to call when the user opens a level to see which animals they've already guessed.

```
GET /api/v1/levels/{levelId}
```

**Response 200:**
```json
{
  "id": 1,
  "title": "Farm Friends",
  "emoji": "\ud83d\udc04",
  "animals": [
    {
      "id": 1,
      "name": "Dog",
      "emoji": "\ud83d\udc15",
      "imageUrl": "/static/images/dog.jpg",
      "guessed": true
    },
    {
      "id": 2,
      "name": "Cat",
      "emoji": "\ud83d\udc08",
      "imageUrl": "/static/images/cat.jpg",
      "guessed": false
    }
    // ... 18 more
  ]
}
```

**Response 404:**
```json
{
  "detail": {
    "error": {
      "code": "level_not_found",
      "message": "Level 999 not found"
    }
  }
}
```

---

### 5. Submit Quiz Answer

Submit the user's guess for an animal. The backend checks correctness, awards coins on first correct guess, and persists the result to Firestore atomically.

```
POST /api/v1/quiz/answer
```

**Request:**
```json
{
  "levelId": 1,
  "animalIndex": 0,
  "answer": "Dog"
}
```
- `levelId`: integer, the level ID (1-6)
- `animalIndex`: integer, zero-based index of the animal within the level (0-19)
- `answer`: string, the user's guess (comparison is **case-insensitive** and **whitespace-trimmed** server-side)

**Response 200 (correct, first time):**
```json
{
  "correct": true,
  "coinsAwarded": 10,
  "totalCoins": 130
}
```

**Response 200 (correct, already guessed):**
```json
{
  "correct": true,
  "coinsAwarded": 0,
  "totalCoins": 130
}
```
Note: `coinsAwarded` is 0 because the user already guessed this animal before. No double-earning.

**Response 200 (wrong answer):**
```json
{
  "correct": false,
  "coinsAwarded": 0,
  "totalCoins": 120,
  "correctAnswer": "Dog"
}
```
Note: `correctAnswer` is **only present when the answer is wrong**. When correct, this field is omitted entirely.

**Response 400:**
```json
{
  "detail": {
    "error": {
      "code": "invalid_request",
      "message": "Invalid levelId or animalIndex"
    }
  }
}
```

---

### 6. Get User Progress

Returns per-level guessed arrays for all 6 levels. Keys are level ID strings, values are boolean arrays (one per animal, in order).

```
GET /api/v1/users/me/progress
```

**Response 200:**
```json
{
  "levels": {
    "1": [true, true, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false],
    "2": [false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false],
    "3": [false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false],
    "4": [false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false],
    "5": [false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false],
    "6": [false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false]
  }
}
```

Use this to compute:
- Per-level progress: count `true` values / total in each array
- Level completion: a level is complete when every value is `true`
- Overall progress: sum of all `true` values across all levels

---

### 7. Get User Coins

Returns just the coin total. Useful for header/navbar display without fetching the full profile.

```
GET /api/v1/users/me/coins
```

**Response 200:**
```json
{
  "totalCoins": 120
}
```

---

### 8. Update Profile

Update the user's display name.

```
PATCH /api/v1/users/me/profile
```

**Request:**
```json
{
  "username": "new_name"
}
```

**Response 200:**
```json
{
  "id": "firebase-uid-abc123",
  "username": "new_name",
  "email": "alice@example.com",
  "totalCoins": 120,
  "createdAt": "2025-01-15T10:30:00Z"
}
```

---

### 9. Leaderboard

Returns a paginated global leaderboard ranked by total coins (descending).

```
GET /api/v1/leaderboard?limit=50&offset=0
```

**Query params:**
- `limit`: max entries (default 50, max 100)
- `offset`: pagination offset (default 0)

**Response 200:**
```json
{
  "entries": [
    {
      "rank": 1,
      "userId": "firebase-uid-xyz",
      "username": "topplayer",
      "totalCoins": 500,
      "levelsCompleted": 3
    },
    {
      "rank": 2,
      "userId": "firebase-uid-abc",
      "username": "alice",
      "totalCoins": 120,
      "levelsCompleted": 0
    }
  ],
  "total": 42
}
```

---

## Data Model (what Firestore stores)

The Flutter app does **not** access Firestore directly, but understanding the data shape helps when interpreting API responses:

```
Firestore collection: users/{uid}
{
  "username": "alice",
  "email": "alice@example.com",
  "total_coins": 120,
  "created_at": <timestamp>,
  "progress": {
    "1": [true, false, true, ...],   // 20 bools per level
    "2": [false, false, ...],
    ...
    "6": [false, false, ...]
  }
}
```

- 6 levels, 20 animals each = 120 animals total
- 10 coins awarded per correct first-time guess
- Maximum possible coins: 1200 (120 animals x 10 coins)
- Progress and coins are updated atomically on answer submission (no partial writes)

---

## Error Handling

All errors follow this format:

```json
{
  "detail": {
    "error": {
      "code": "machine_readable_code",
      "message": "Human-readable description"
    }
  }
}
```

| HTTP Status | Code | Meaning |
|---|---|---|
| 401 | - | Invalid/expired token. Refresh and retry. |
| 404 | `user_not_found` | Profile not registered. Call POST /auth/register. |
| 404 | `level_not_found` | Invalid level ID. |
| 409 | `profile_exists` | Register called twice. Safe to ignore, proceed normally. |
| 400 | `invalid_request` | Bad levelId or animalIndex in answer submission. |
| 422 | - | Validation error (e.g. username too short). Body has pydantic details. |
| 429 | - | Rate limited (100 requests/minute per IP). |

---

## Recommended Flutter API Call Map

| Screen / Action | API Call | When |
|---|---|---|
| App startup after sign-in | `POST /auth/register` then `GET /auth/me` | Once per session start |
| Home screen | `GET /levels` | On navigation to home |
| Level screen | `GET /levels/{id}` | When user taps into a level |
| Quiz guess | `POST /quiz/answer` | On each answer submission |
| After correct answer | Update local state from response `totalCoins` + mark animal guessed | No extra API call needed |
| Profile/settings | `GET /auth/me` | On navigation to profile |
| Edit username | `PATCH /users/me/profile` | On save |
| Leaderboard | `GET /leaderboard` | On navigation to leaderboard |
| Coin display (header) | `GET /users/me/coins` | Periodic refresh or pull-to-refresh |
| Progress overview | `GET /users/me/progress` | On navigation to progress screen |

### Optimistic updates

After `POST /quiz/answer` returns, the response contains `coinsAwarded` and `totalCoins`. Update the local UI state immediately from the response without making a separate `GET /users/me/coins` call. Similarly, mark the animal at `animalIndex` as guessed locally after a correct answer.

### Data persistence note

All game data (progress, coins) is persisted server-side in Firestore. If the user signs in on a new device, all progress will be available as soon as they authenticate. The Flutter app does **not** need to store progress locally (though local caching for offline display is fine as a UX enhancement).
