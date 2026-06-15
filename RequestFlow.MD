## AI Cloud Cost Detective - Request Flow

```
①  User ─·─·─► React ─·─·─► FastAPI Auth ─·─·─► JWT (Docker PostgreSQL)

②  User selects AWS Region ─·─·─► Python Backend

③  Python ─·─·─► Thread Pool (AWS CLI) ─·─·─► Fetches all resources in Region concurrently

④  Python ─·─·─► FastAPI WebSocket ─·─·─► React (Streams live progress & timer)

⑤  Python ─·─·─► Gemini / Groq API ─·─·─► Generates cost analysis & automated fix commands

⑥  Python ─·─·─► Docker PostgreSQL ─·─·─► Stores analysis history & calculated duration

⑦  React ◄·─·─·─ Displays final report with cost breakdowns, suggestions, and fixes
```
