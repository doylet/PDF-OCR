# PDF-OCR Frontend (Next.js)

Next.js application with PDF.js for region-based data extraction visualization.

## Features

- PDF upload and visualization with PDF.js
- Canvas-based region selection (click and drag)
- Real-time job status polling
- Multiple export formats (CSV, TSV, JSON)
- Responsive UI with Tailwind CSS

## Prerequisites

- Node.js 18+
- npm or yarn
- Backend API running (see `../backend/README.md`)

## Installation

```bash
npm install
```

## Configuration

Create `.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=your-api-key
```

For production:

```env
NEXT_PUBLIC_API_URL=https://your-backend.run.app
NEXT_PUBLIC_API_KEY=your-production-api-key
```

## Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Build

```bash
npm run build
npm start
```

## Deployment

### Cloud Run (Recommended)

```bash
./deploy.sh
```

The script will build and deploy the Next.js app to Cloud Run.

### Manual Deployment

See `../DEPLOYMENT.md` for manual Docker build instructions.

## License

MIT
