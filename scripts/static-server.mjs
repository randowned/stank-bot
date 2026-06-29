// Minimal static file server with SPA fallback and HTTP proxy (no WebSocket proxy).
// Used by Playwright webServer to avoid Vite WS proxy crashes under parallel workers.
// Dependencies: none (uses Node.js built-in modules only).

import { createServer } from 'http';
import { readFileSync, existsSync, statSync } from 'fs';
import { extname, join, resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import http from 'http';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..');
const buildDir = resolve(repoRoot, 'src/stankbot/web/frontend/build');
const port = parseInt(process.env.PORT || '4173', 10);
const backendTarget = 'http://127.0.0.1:8000';

const MIME_MAP = {
    '.html': 'text/html',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.webp': 'image/webp',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.txt': 'text/plain',
    '.map': 'application/octet-stream',
};

function serveStatic(res, filePath) {
    if (!existsSync(filePath) || !statSync(filePath).isFile()) {
        return false;
    }
    const ext = extname(filePath).toLowerCase();
    const mime = MIME_MAP[ext] || 'application/octet-stream';
    const content = readFileSync(filePath);
    res.writeHead(200, {
        'Content-Type': mime,
        'Content-Length': content.length,
        'Cache-Control': 'no-cache',
    });
    res.end(content);
    return true;
}

function proxyRequest(req, res) {
    const url = new URL(req.url, backendTarget);
    const options = {
        hostname: url.hostname,
        port: url.port,
        path: url.pathname + url.search,
        method: req.method,
        headers: { ...req.headers },
    };
    // Remove host header to let the proxy set it correctly
    delete options.headers.host;

    const proxyReq = http.request(options, (proxyRes) => {
        res.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(res);
    });

    proxyReq.on('error', (err) => {
        console.error(`Proxy error for ${req.url}:`, err.message);
        res.writeHead(502);
        res.end('Bad Gateway');
    });

    req.pipe(proxyReq);
}

const server = createServer((req, res) => {
    const url = new URL(req.url, `http://localhost:${port}`);

    // Proxy API, auth, healthz, ping to backend (HTTP only, no WebSocket)
    if (url.pathname.startsWith('/api/') ||
        url.pathname.startsWith('/auth/') ||
        url.pathname === '/healthz' ||
        url.pathname === '/ping') {
        console.log(`[proxy] ${req.method} ${req.url}`);
        return proxyRequest(req, res);
    }

    // WebSocket upgrade requests — reject explicitly (avoids hanging sockets)
    if (req.headers.upgrade?.toLowerCase() === 'websocket') {
        console.log(`[ws] Rejecting WebSocket upgrade: ${req.url}`);
        res.writeHead(426, { 'Content-Type': 'text/plain' });
        res.end('Upgrade Required — WebSocket proxying disabled for parallel E2E stability');
        return;
    }

    // Serve static files from build dir
    let filePath = join(buildDir, url.pathname === '/' ? 'index.html' : url.pathname);

    if (serveStatic(res, filePath)) return;

    // SPA fallback — serve index.html for unrecognized paths
    const indexPath = join(buildDir, 'index.html');
    if (existsSync(indexPath)) {
        const content = readFileSync(indexPath);
        res.writeHead(200, { 'Content-Type': 'text/html', 'Cache-Control': 'no-cache' });
        res.end(content);
    } else {
        res.writeHead(404);
        res.end('Not Found');
    }
});

server.listen(port, () => {
    console.log(`Static server listening on http://localhost:${port}`);
    console.log(`  Serving: ${buildDir}`);
    console.log(`  Proxying: /api/, /auth/, /healthz, /ping -> ${backendTarget}`);
});
