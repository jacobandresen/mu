---
name: no-server-in-tests
description: HTTP server testing rules — use in-process test clients, never start a real server. Apply to any task that has an HTTP server and a test file.
---

The test command must never start the application server as a subprocess.
A real server blocks the process and cannot be stopped by the test runner,
causing the test suite to hang or fail with "address already in use".

## The failure pattern

```makefile
test:
	./myapp &       # starts server — blocks or races
	curl localhost:8080/ping
```

```
FAIL: dial tcp: connect: connection refused   # server not ready yet
# or
FAIL: listen tcp :8080: bind: address already in use
```

## Rule: use the framework's in-process test client

Each framework provides a way to call handlers directly in-process, with
no real port:

**Go (Gin / net/http):**
```go
func TestPing(t *testing.T) {
    router := setupRouter()   // returns *gin.Engine, does not call Run()
    w := httptest.NewRecorder()
    req, _ := http.NewRequest("GET", "/ping", nil)
    router.ServeHTTP(w, req)
    assert.Equal(t, 200, w.Code)
}
```
Test command: `go test ./...`

**Python (Flask):**
```python
def test_ping(client):   # client = app.test_client() via fixture
    resp = client.get("/ping")
    assert resp.status_code == 200
```
Test command: `.venv/bin/pytest` — never `flask run`

**C# (ASP.NET Core):**
```csharp
public class ApiTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;
    public ApiTests(WebApplicationFactory<Program> f) => _client = f.CreateClient();

    [Fact]
    public async Task GetPing_Returns200()
    {
        var resp = await _client.GetAsync("/ping");
        Assert.Equal(HttpStatusCode.OK, resp.StatusCode);
    }
}
```
Test command: `dotnet test` — no server process started.

**Node.js (Express):**
```js
const request = require('supertest');
const app = require('./app');   // exports the express app, does NOT call listen()

test('GET /ping', async () => {
    const res = await request(app).get('/ping');
    expect(res.statusCode).toBe(200);
});
```
Test command: `npx jest` — supertest handles the port internally.

## Rule: the app module must not call listen/Run at import time

Separate app construction from startup:

```js
// app.js — exports the app, no listen()
const express = require('express');
const app = express();
app.get('/ping', (req, res) => res.json({ status: 'ok' }));
module.exports = app;

// server.js — only file that calls listen()
const app = require('./app');
app.listen(8080);
```

```python
# app.py — defines app, no app.run()
from flask import Flask
app = Flask(__name__)

# run.py or __main__ block only
if __name__ == "__main__":
    app.run()
```

## Rule: Makefile `test:` must call the test runner, not the application

```makefile
# Wrong — starts a server, blocks forever:
test:
	make run

# Right — calls the test runner directly:
test:
	go test ./...
```
