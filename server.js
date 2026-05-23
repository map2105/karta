// ─────────────────────────────────────────────────────────────
//  server.js — Express-сервер для интерактивной карты России
//  Раздаёт статику + роут /ping для мониторинга (UptimeRobot)
//  Деплой: Railway (или любой Node.js-хостинг)
// ─────────────────────────────────────────────────────────────

const express = require('express');
const path    = require('path');

const app  = express();
const PORT = process.env.PORT || 3000;

// ── Статические файлы (HTML, CSS, JS, SVG, медиа) ────────────
app.use(express.static(path.join(__dirname, '.')));

// ── /ping — для UptimeRobot / мониторинга ────────────────────
app.get('/ping', (_req, res) => {
  res.json({ status: 'ok', ts: new Date().toISOString() });
});

// ── Fallback: любой путь → index.html (SPA-режим) ────────────
app.get('*', (_req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`🗺️  Карта запущена: http://localhost:${PORT}`);
});
