// StankBot agent browser launcher (cross-platform Node.js)
// Starts the Python backend + Vite frontend, health-polls both,
// authenticates via mock-login, then opens a headed Playwright browser
// for agent-driven UX review and debugging. Cleans up on exit.
//
// Usage:
//   node scripts/agent-browser.mjs
//   node scripts/agent-browser.mjs --headless
//   node scripts/agent-browser.mjs --persistent
//
// Cleanup is automatic on SIGINT/SIGTERM/exit.

import { spawn } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import * as fs from 'fs';
import * as http from 'http';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..');
const backendPidFile = resolve(repoRoot, '.stankbot_backend.pid');
const frontendPidFile = resolve(repoRoot, '.stankbot_frontend.pid');
const backendLogFile = resolve(repoRoot, '.stankbot_backend.log');
const frontendLogFile = resolve(repoRoot, '.stankbot_frontend.log');
const frontendDir = resolve(repoRoot, 'src/stankbot/web/frontend');

// ---- CLI flags ----
const args = process.argv.slice(2);
const headless = args.includes('--headless');
const persistent = args.includes('--persistent');

// ---- Helpers ----
function healthCheck(port) {
    return new Promise((resolve) => {
        const req = http.get(`http://localhost:${port}/healthz`, (res) => {
            let body = '';
            res.on('data', (chunk) => (body += chunk));
            res.on('end', () => resolve(res.statusCode === 200));
        });
        req.on('error', () => resolve(false));
        req.setTimeout(2000, () => { req.destroy(); resolve(false); });
    });
}

function httpGet(port, path = '/') {
    return new Promise((resolve) => {
        const req = http.get(`http://localhost:${port}${path}`, (res) => {
            let body = '';
            res.on('data', (chunk) => (body += chunk));
            res.on('end', () => resolve(res.statusCode < 400 ? body : null));
        });
        req.on('error', () => resolve(null));
        req.setTimeout(2000, () => { req.destroy(); resolve(null); });
    });
}

function tail(file, lines = 20) {
    try {
        const content = fs.readFileSync(file, 'utf-8');
        const all = content.split('\n').filter(Boolean);
        return all.slice(-lines).join('\n');
    } catch { return '(log file empty or missing)'; }
}

function killByPidFile(pidFile) {
    return new Promise((resolve) => {
        try {
            const pidStr = fs.readFileSync(pidFile, 'utf-8').trim();
            const pid = parseInt(pidStr, 10);
            if (!pid) { resolve(); return; }
            console.log(`Shutting down process ${pid}...`);
            if (process.platform === 'win32') {
                const wmic = spawn('cmd', ['/c', `wmic process where processid=${pid} call terminate >nul 2>&1`], { stdio: 'ignore' });
                wmic.on('close', () => { try { fs.unlinkSync(pidFile); } catch {} resolve(); });
            } else {
                try { process.kill(pid, 'SIGTERM'); } catch {}
                setTimeout(() => {
                    try { process.kill(pid, 'SIGKILL'); } catch {}
                    try { fs.unlinkSync(pidFile); } catch {}
                    resolve();
                }, 2000);
            }
        } catch { resolve(); }
    });
}

async function killPort(port) {
    return new Promise((resolve) => {
        if (process.platform === 'win32') {
            const findPid = spawn('cmd', ['/c', `netstat -ano | findstr :${port} | findstr LISTENING`], { stdio: 'pipe' });
            let output = '';
            findPid.stdout.on('data', (chunk) => (output += chunk));
            findPid.on('close', () => {
                const lines = output.trim().split(/\r?\n/);
                const pids = new Set();
                for (const line of lines) {
                    const parts = line.trim().split(/\s+/);
                    const pid = parseInt(parts[parts.length - 1], 10);
                    if (pid > 0) pids.add(pid);
                }
                if (pids.size > 0) {
                    console.log(`Killing stale process(es) on port ${port}: ${[...pids].join(', ')}`);
                    let killed = 0;
                    for (const pid of pids) {
                        const wmic = spawn('cmd', ['/c', `wmic process where processid=${pid} call terminate >nul 2>&1`], { stdio: 'ignore' });
                        wmic.on('close', () => { killed++; if (killed === pids.size) setTimeout(resolve, 1000); });
                    }
                } else { resolve(); }
            });
        } else {
            const findPid = spawn('sh', ['-c', `lsof -ti :${port} 2>/dev/null`], { stdio: 'pipe' });
            let output = '';
            findPid.stdout.on('data', (chunk) => (output += chunk));
            findPid.on('close', () => {
                const pids = output.trim().split(/\s+/).map(Number).filter(Boolean);
                for (const pid of pids) {
                    try { process.kill(pid, 'SIGKILL'); } catch {}
                }
                pids.length > 0 ? setTimeout(resolve, 1000) : resolve();
            });
        }
    });
}

async function mockLogin() {
    return new Promise((resolve, reject) => {
        const body = JSON.stringify({ user_id: 111111111, username: 'AgentUser', guild: 123456789 });
        const req = http.request({
            hostname: 'localhost',
            port: 8000,
            path: '/auth/mock-login',
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) }
        }, (res) => {
            let data = '';
            res.on('data', (chunk) => (data += chunk));
            res.on('end', () => resolve(res.statusCode < 400));
        });
        req.on('error', (err) => reject(err));
        req.write(body);
        req.end();
    });
}

// ---- Run playwright-cli command ----
function runPlaywrightCli(cmd, session = 'stankbot') {
    return new Promise((resolve, reject) => {
        const isWin = process.platform === 'win32';
        const args = ['-s=' + session, ...cmd.split(' ')];
        if (headless) args.splice(1, 0, '--headless');
        if (persistent && cmd.startsWith('open')) args.push('--persistent');

        const proc = spawn(isWin ? 'npx.cmd' : 'npx', ['--no-install', 'playwright-cli', ...args], {
            cwd: repoRoot,
            stdio: ['ignore', 'pipe', 'pipe'],
            shell: isWin,
        });

        let output = '';
        proc.stdout.on('data', (chunk) => (output += chunk));
        proc.stderr.on('data', (chunk) => (output += chunk));
        proc.on('close', (code) => {
            if (code !== 0 && !cmd.startsWith('close')) {
                console.error(`playwright-cli "${cmd}" exited with code ${code}`);
                if (output.length < 2000) console.error(output);
            }
            resolve({ code, output });
        });
        proc.on('error', reject);
    });
}

// ---- Main ----
async function main() {
    console.log('=== StankBot Agent Browser ===\n');

    // Kill stale processes
    console.log('Cleaning up stale processes...');
    await killPort(8000);
    await killPort(5173);
    await new Promise((r) => setTimeout(r, 1000));

    // Start backend
    console.log('Starting backend (ENV=dev-mock)...');
    const env = { ...process.env, ENV: 'dev-mock', PYTHONPATH: resolve(repoRoot, 'src') };
    const backendLogStream = fs.createWriteStream(backendLogFile, { flags: 'w' });
    const backend = spawn('python', ['-m', 'stankbot'], {
        cwd: repoRoot, env, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true,
    });
    backend.stdout.pipe(backendLogStream);
    backend.stderr.pipe(backendLogStream);
    fs.writeFileSync(backendPidFile, String(backend.pid));
    console.log(`Backend PID: ${backend.pid}`);

    backend.on('exit', () => { /* process being torn down */ });

    // Wait for backend
    process.stdout.write('Waiting for backend...');
    for (let i = 0; i < 60; i++) {
        if (backend.exitCode !== null) {
            console.log('\nERROR: Backend process died during startup.');
            console.error(tail(backendLogFile));
            process.exit(1);
        }
        if (await healthCheck(8000)) { console.log(' ready.'); break; }
        if (i === 59) { console.log('\nERROR: Backend did not become ready within 30s.'); process.exit(1); }
        await new Promise((r) => setTimeout(r, 500));
    }

    // Start frontend
    console.log('Starting frontend (Vite)...');
    const frontendLogStream = fs.createWriteStream(frontendLogFile, { flags: 'w' });
    const isWin = process.platform === 'win32';
    const frontend = spawn(isWin ? 'npx.cmd' : 'npx', ['vite', 'dev', '--strictPort'], {
        cwd: frontendDir, env, stdio: ['ignore', 'pipe', 'pipe'], shell: isWin, windowsHide: true,
    });
    frontend.stdout.pipe(frontendLogStream);
    frontend.stderr.pipe(frontendLogStream);
    fs.writeFileSync(frontendPidFile, String(frontend.pid));
    console.log(`Frontend PID: ${frontend.pid}`);

    // Wait for frontend
    process.stdout.write('Waiting for frontend...');
    for (let i = 0; i < 60; i++) {
        if (frontend.exitCode !== null) {
            console.log('\nERROR: Frontend process died during startup.');
            console.error(tail(frontendLogFile));
            process.exit(1);
        }
        const body = await httpGet(5173);
        if (body && body.includes('<!doctype html')) { console.log(' ready.'); break; }
        if (i === 59) { console.log('\nERROR: Frontend did not become ready within 30s.'); process.exit(1); }
        await new Promise((r) => setTimeout(r, 500));
    }

    // Authenticate
    console.log('Authenticating...');
    await mockLogin();
    console.log('  Mock login: OK');

    // Open browser
    console.log('\n=== Opening browser ===');
    const headedFlag = headless ? '' : '--headed';
    const persistentFlag = persistent ? '--persistent' : '';
    await runPlaywrightCli(`open http://localhost:5173 ${headedFlag} ${persistentFlag}`);

    // Inject auth state into the page
    const evalScript = `eval "async () => {
        sessionStorage.removeItem('stankbot:auth');
        sessionStorage.removeItem('stankbot:guilds');
        const v = await fetch('/api/version').then(r => r.json());
        localStorage.setItem('stankbot:version', v.version);
        const res = await fetch('/auth/mock-login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id:111111111,username:'AgentUser',guild:123456789})
        });
        return res.ok ? 'authenticated' : await res.text();
    }"`;
    await runPlaywrightCli(evalScript);

    // Reload to apply auth
    await runPlaywrightCli('reload');

    console.log('\n=== Agent browser ready ===');
    console.log('  Backend:  http://localhost:8000');
    console.log('  Frontend: http://localhost:5173');
    console.log('  Browser:  headed session "stankbot"');
    console.log('\nPress Ctrl+C to stop all processes.\n');

    // Wait for Ctrl+C or browser close
    return new Promise((resolve) => {
        let pollCount = 0;
        const pollTimer = setInterval(async () => {
            pollCount++;
            // Every 10 seconds, check if the playwright-cli session is still alive
            if (pollCount % 5 === 0) {
                const { output } = await runPlaywrightCli('list');
                if (!output.includes('stankbot')) {
                    console.log('\nBrowser closed. Shutting down...');
                    clearInterval(pollTimer);
                    resolve();
                }
            }
            // Timeout after 30 minutes
            if (pollCount > 900) {
                console.log('\n30-minute timeout reached. Shutting down...');
                clearInterval(pollTimer);
                resolve();
            }
        }, 2000);
        // Stop polling on SIGINT/SIGTERM
        process.on('SIGINT', () => { clearInterval(pollTimer); resolve(); });
        process.on('SIGTERM', () => { clearInterval(pollTimer); resolve(); });
    });
}

// ---- Run ----
main()
    .catch((err) => {
        console.error('Agent browser failed:', err);
        process.exit(1);
    })
    .finally(async () => {
        // Close browser
        try { await runPlaywrightCli('close', 'stankbot'); } catch {}
        // Kill backend + frontend
        await killByPidFile(backendPidFile);
        await killByPidFile(frontendPidFile);
        console.log(`Backend log: ${backendLogFile}`);
        console.log(`Frontend log: ${frontendLogFile}`);
    });
