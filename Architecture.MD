## AI Cloud Cost Detective - Architecture

```
                               ┌──────────────┐
                               │     USER     │
                               └──────┬───────┘
                                      │
                                      ▼
                            ┌───────────────────┐
                            │  REACT FRONTEND   │
                            │  (Vite + TS)      │
                            └────────┬──────────┘
                                     :
                                     : Login / Select Region
                                     ▼
                            ┌───────────────────┐
                            │  PYTHON BACKEND   │
                            │    (FastAPI)      │
                            │                   │
                            │  · JWT Auth       │
                            │  · Thread Pool    │
                            └───┬───────┬───┬───┘
                                :       :   :
                 ┌──────────────┘       :   └──────────────┐
                 :                      :                  :
                 ▼                      ▼                  ▼
          ┌─────────────┐     ┌──────────────┐    ┌──────────────┐
          │   AWS CLI   │     │   FASTAPI    │    │   GEMINI /   │
          │             │     │  WEBSOCKET   │    │    GROQ      │
          │ aws ec2 ... │     │  (Progress)  │    │              │
          │ aws s3 ...  │     └──────┬───────┘    │ Cost Analysis│
          └──────┬──────┘            :            └──────┬───────┘
                 :                   : Live logs         :
                 ▼                   ▼                   :
          ┌─────────────┐   ┌───────────────┐            :
          │    AWS      │   │    REACT      │            :
          │  (us-east-1)│   │  (Live Timer &│            :
          │             │   │   Progress)   │            :
          └─────────────┘   └───────────────┘            :
                                                         ▼
                                                  ┌──────────────┐
                                                  │  POSTGRESQL  │
                                                  │   (Docker)   │
                                                  │              │
                                                  │ · users      │
                                                  │ · analyses   │
                                                  └──────┬───────┘
                                                         :
                                                         : Stored results
                                                         ▼
                                                  ┌───────────────┐
                                                  │    REACT      │
                                                  │ (Final Report │
                                                  │  + Suggestions│
                                                  │  + Fixes)     │
                                                  └───────────────┘
```
