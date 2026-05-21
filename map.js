// ─────────────────────────────────────────────────────────────
//  map.js — логика интерактивной карты России
//  SVG загружается инлайн через fetch, клики прямо по <path>
// ─────────────────────────────────────────────────────────────

let activeRegion = null;

// ── Иконки по расширению файла ────────────────────────────────
function fileIcon(path) {
  const ext = path.split('.').pop().toLowerCase();
  const map = {
    mp4:'🎬', avi:'🎬', mkv:'🎬', mov:'🎬', wmv:'🎬',
    mp3:'🎵', wav:'🎵', flac:'🎵',
    jpg:'🖼️', jpeg:'🖼️', png:'🖼️', gif:'🖼️', webp:'🖼️', bmp:'🖼️',
    pdf:'📄',
    txt:'📝', doc:'📝', docx:'📝', rtf:'📝',
    ppt:'📊', pptx:'📊', xls:'📊', xlsx:'📊',
  };
  return map[ext] || '📁';
}

// ── Боковая панель ────────────────────────────────────────────
function openSidebar(regionId) {
  // Снять выделение с предыдущего
  if (activeRegion) {
    const prev = document.getElementById(activeRegion);
    if (prev) prev.classList.remove('active');
  }

  // Выделить новый
  activeRegion = regionId;
  const el = document.getElementById(regionId);
  if (el) el.classList.add('active');

  // Данные из config.js
  const data = CONFIG.regions[regionId];
  const name = data ? data.name : (el ? el.getAttribute('data-name') : regionId);
  const files = data ? data.files : [];

  document.getElementById('sidebarTitle').textContent = name;

  const list = document.getElementById('fileList');
  list.innerHTML = '';

  if (!files || files.length === 0) {
    list.innerHTML = '<li class="empty-msg">Файлы не добавлены</li>';
  } else {
    files.forEach(f => {
      const ext = f.path.split('.').pop().toLowerCase();
      const li  = document.createElement('li');
      li.innerHTML = `
        <a class="file-item" href="${f.path}" target="_blank">
          <span class="file-icon">${fileIcon(f.path)}</span>
          <span class="file-info">
            <span class="file-name">${f.name}</span>
            <span class="file-ext">${ext}</span>
          </span>
        </a>`;
      list.appendChild(li);
    });
  }

  document.getElementById('sidebar').classList.add('open');
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  if (activeRegion) {
    const el = document.getElementById(activeRegion);
    if (el) el.classList.remove('active');
    activeRegion = null;
  }
}

// ── Подсчёт регионов с файлами ────────────────────────────────
function countLocations() {
  if (!CONFIG || !CONFIG.regions) return 0;
  return Object.values(CONFIG.regions).filter(r => r.files && r.files.length > 0).length;
}

// ── Перевод lat/lon → SVG координаты (та же проекция что в build_svg.py) ──
const SVG_X0    = 103,   SVG_Y0    = 103;
const SVG_PX_W  = 20326, SVG_PX_H  = 9667;
const LON0 = 20, LAT0 = 81, LON_RANGE = 170, LAT_RANGE = 40;
const VIEWBOX_W = 20955, VIEWBOX_H = 11530;

function latLonToSvg(lat, lon) {
  const x = SVG_X0 + (lon - LON0) / LON_RANGE * SVG_PX_W;
  const y = SVG_Y0 + (LAT0 - lat) / LAT_RANGE * SVG_PX_H;
  return { x, y };
}

// ── Фон: фон, соседние страны и подписи морей встроены в russia.svg ────────
// buildBackground() оставлена для совместимости, но больше не нужна
function buildBackground(svgEl) {
  // Всё необходимое (defs, морской фон, штриховка соседей, подписи морей)
  // теперь генерируется скриптом build_svg.py и встроено прямо в russia.svg.
}

// ── Маркеры городов (рисуются поверх регионов прямо в SVG) ────
function buildMarkers(svgEl) {
  if (!CONFIG || !CONFIG.regions) return;

  // Группа маркеров — рисуется поверх всех путей
  let markerGroup = svgEl.querySelector('#markerGroup');
  if (!markerGroup) {
    markerGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    markerGroup.setAttribute('id', 'markerGroup');
    svgEl.appendChild(markerGroup);
  }

  // Размер маркера в SVG-единицах
  // При ширине SVG 20955 и реальной ширине ~1500px → 1px ≈ 14 SVG ед.
  // Делаем радиус ~80 SVG ед. ≈ 5-6 пикселей на экране
  const R  = 80;   // радиус кружка
  const R2 = 110;  // радиус внешнего кольца (hover/active)

  Object.entries(CONFIG.regions).forEach(([id, region]) => {
    if (!region.pin) return;
    const { lat, lon } = region.pin;
    const { x, y } = latLonToSvg(lat, lon);

    // Создаём группу маркера
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('class', 'map-marker');
    g.setAttribute('data-region', id);
    g.setAttribute('cursor', 'pointer');

    // Внешнее кольцо (белое, для контраста)
    const ring = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    ring.setAttribute('cx', x);
    ring.setAttribute('cy', y);
    ring.setAttribute('r', R2);
    ring.setAttribute('fill', 'white');
    ring.setAttribute('opacity', '0.85');
    ring.setAttribute('class', 'marker-ring');

    // Основной кружок
    const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    dot.setAttribute('cx', x);
    dot.setAttribute('cy', y);
    dot.setAttribute('r', R);
    dot.setAttribute('fill', '#c0392b');
    dot.setAttribute('class', 'marker-dot');

    g.appendChild(ring);
    g.appendChild(dot);

    // Клик — открывает ту же боковую панель
    g.addEventListener('click', e => {
      e.stopPropagation();
      openSidebar(id);
    });

    markerGroup.appendChild(g);
  });
}

// ── Навесить обработчики на все <path> в SVG ──────────────────
function bindRegionClicks(svgEl) {
  const paths = svgEl.querySelectorAll('path[id]');
  paths.forEach(path => {
    const id = path.getAttribute('id');
    if (!id || !id.startsWith('RU-')) return;

    // Подсветить регионы у которых есть файлы
    if (CONFIG.regions[id] && CONFIG.regions[id].files && CONFIG.regions[id].files.length > 0) {
      path.classList.add('has-data');
    }

    path.addEventListener('click', e => {
      e.stopPropagation();
      openSidebar(id);
    });
  });
}

// ── Загрузка SVG инлайн ───────────────────────────────────────
async function loadSVG() {
  const container = document.getElementById('svgContainer');

  try {
    // fetch работает только при запуске через сервер.
    // При file:// используем XMLHttpRequest как запасной вариант.
    let svgText;
    try {
      const resp = await fetch('russia.svg');
      svgText = await resp.text();
    } catch {
      svgText = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('GET', 'russia.svg', true);
        xhr.onload  = () => resolve(xhr.responseText);
        xhr.onerror = () => reject(new Error('XHR failed'));
        xhr.send();
      });
    }

    container.innerHTML = svgText;
    const svgEl = container.querySelector('svg');
    if (!svgEl) throw new Error('SVG element not found');

    // SVG должен занимать весь контейнер
    svgEl.setAttribute('width', '100%');
    svgEl.setAttribute('height', '100%');

    buildBackground(svgEl);   // фон, моря, подписи — вставляется ДО всех путей
    bindRegionClicks(svgEl);
    buildMarkers(svgEl);

    // Клик по фону карты (не по region) закрывает панель
    svgEl.addEventListener('click', () => closeSidebar());

  } catch (err) {
    console.error('Ошибка загрузки SVG:', err);
    container.innerHTML = `
      <div style="padding:20px;color:#c00;">
        <b>Ошибка загрузки карты</b><br>
        ${err.message}<br><br>
        Откройте через <b>открыть.bat</b> или локальный сервер.
      </div>`;
  }
}

// ── Инициализация ─────────────────────────────────────────────
function init() {
  const count = countLocations();
  document.getElementById('locationCount').textContent =
    count > 0 ? count + ' локаций' : '';

  loadSVG();

  document.getElementById('closeBtn').addEventListener('click', e => {
    e.stopPropagation();
    closeSidebar();
  });
}

document.addEventListener('DOMContentLoaded', init);
