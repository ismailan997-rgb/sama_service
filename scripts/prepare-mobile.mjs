import { cp, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const configuredApiUrl = process.env.SAMASERVICE_API_URL?.trim()
    || 'https://sama-service-1.onrender.com/api';

let apiUrl;
try {
    apiUrl = new URL(configuredApiUrl);
} catch {
    throw new Error('SAMASERVICE_API_URL doit être une URL HTTPS valide terminant par /api');
}

if (apiUrl.protocol !== 'https:' || !apiUrl.pathname.replace(/\/+$/, '').endsWith('/api')) {
    throw new Error('SAMASERVICE_API_URL doit être une URL HTTPS valide terminant par /api');
}

const webRoot = path.join(projectRoot, 'mobile', 'www');
const staticRoot = path.join(webRoot, 'static');

await mkdir(staticRoot, { recursive: true });
await cp(path.join(projectRoot, 'index.html'), path.join(webRoot, 'index.html'));
await cp(path.join(projectRoot, 'static'), staticRoot, { recursive: true });
await writeFile(
    path.join(staticRoot, 'mobile-config.js'),
    `window.SAMASERVICE_API_URL = ${JSON.stringify(apiUrl.href.replace(/\/+$/, ''))};\nwindow.SAMASERVICE_IS_NATIVE = true;\n`,
    'utf8'
);

console.log(`Fichiers mobiles préparés pour ${apiUrl.origin}`);