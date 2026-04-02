# QSOP React Dashboard

A modern React + TypeScript dashboard for the Quantum-Safe Optimization Platform.

## Features

- 🎨 Modern dark theme with Tailwind CSS
- 📊 Real-time job monitoring with auto-refresh
- 🔐 Secure authentication with PQC-signed JWTs
- 📝 Job submission form for QAOA, VQE, Annealing
- 🔑 PQC key management
- 📱 Responsive design for desktop and mobile

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **TanStack Query** - Data fetching and caching
- **Zustand** - State management
- **Axios** - HTTP client
- **Lucide React** - Icons
- **Recharts** - Charts (optional)

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
frontend-react/
├── src/
│   ├── api/
│   │   └── client.ts          # API client with full type safety
│   ├── components/
│   │   ├── Dashboard.tsx      # Main dashboard view
│   │   ├── JobsList.tsx       # Job listing with status
│   │   ├── JobForm.tsx        # Job submission form
│   │   ├── Layout.tsx         # App layout with sidebar
│   │   └── Login.tsx          # Login page
│   ├── hooks/
│   │   ├── useApi.ts          # React Query hooks
│   │   └── useAuth.ts         # Authentication state
│   ├── types/
│   │   └── index.ts           # TypeScript type definitions
│   ├── App.tsx                # Main app component
│   ├── main.tsx               # Entry point
│   └── index.css              # Global styles
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## Configuration

The app proxies API requests to the backend:

```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/ws': 'ws://localhost:8000',
  }
}
```

## Development

### Type Checking

```bash
npm run typecheck
```

### Linting

```bash
npm run lint
```

## API Integration

The dashboard connects to the QSOP API:

| Endpoint                       | Description    |
| ------------------------------ | -------------- |
| `POST /api/v1/auth/login`      | Login          |
| `GET /api/v1/jobs`             | List jobs      |
| `POST /api/v1/jobs`            | Submit job     |
| `GET /api/v1/jobs/:id`         | Get job status |
| `POST /api/v1/jobs/:id/cancel` | Cancel job     |
| `GET /health`                  | Health check   |

## Screenshots

### Dashboard

Shows system status, crypto status, and recent jobs.

### Job Submission

Select algorithm, backend, configure parameters, submit.

### Jobs List

View all jobs with real-time status updates.

## Building for Production

```bash
npm run build
```

Output in `dist/` directory. Serve with any static file server:

```bash
npm run preview
# or
npx serve dist
```

## Docker

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
```

## License

MIT
