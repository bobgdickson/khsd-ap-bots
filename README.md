# khsd-ap-bots
## API Endpoints

Once the server is running (for example via `uvicorn app.main:app --reload`), the following endpoints are available:

- **GET** `/runids`
  : List all distinct run IDs in the process log.
- **GET** `/runids/{runid}/status_counts`
  : Retrieve counts of each status for the specified run ID.
- **DELETE** `/runids/{runid}`
  : Remove all log entries associated with the specified run ID.
