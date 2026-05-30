// ─────────────────────────────────────────────────────────────
//  map.js — логика интерактивной карты России
//  SVG загружается инлайн через fetch, клики прямо по <path>
// ─────────────────────────────────────────────────────────────

let activeRegion = null;
let _graticuleObserver = null;   // ResizeObserver для пересчёта сетки
let _svgEl = null;               // ссылка на загруженный SVG

// Состояние zoom/pan инициализируется после объявления констант VIEWBOX_*
let _vbX = 0, _vbY = 0, _vbW = 0, _vbH = 0;
// Ширина viewBox для полного вида — вычисляется один раз при первой загрузке.
// Фиксирована, чтобы Россия выглядела одинаково в обычном и полноэкранном режиме.
let _fullVbW = 0;

// ── Иконки по расширению файла ────────────────────────────────
function fileIcon(path) {
  if (/vkvideo\.ru|vk\.com\/video|rutube\.ru/i.test(path)) return '🎬';
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

// ── Категории файлов ──────────────────────────────────────────
const EXT_VIDEO  = new Set(['mp4','avi','mkv','mov','wmv','webm']);
const EXT_IMAGE  = new Set(['jpg','jpeg','png','gif','webp','bmp','svg']);
const EXT_TEXT   = new Set(['txt','md']);
const EXT_PPTX   = new Set(['ppt','pptx']);
const EXT_PDF    = new Set(['pdf']);

function extOf(path) { return (path || '').split('.').pop().toLowerCase().split('?')[0]; }
function isVideo(path)  { return EXT_VIDEO.has(extOf(path)); }
function isImage(path)  { return EXT_IMAGE.has(extOf(path)); }
function isText(path)   { return EXT_TEXT.has(extOf(path)); }

// ── Определение embed-источника (VK, Rutube и др.) ────────────
// Возвращает { type: 'embed', embedUrl } или null
function detectEmbed(file) {
  // Явно задан тип embed в конфиге: { type: 'embed', path: '...' }
  if (file.type === 'embed') return { embedUrl: file.path };

  const url = file.path || '';

  // VK Видео — форматы:
  //   https://vkvideo.ru/video_ext.php?...
  //   https://vk.com/video_ext.php?...
  //   https://vk.com/video-XXXXX_XXXXX
  if (/vk\.com\/video_ext|vkvideo\.ru\/video_ext/i.test(url)) {
    return { embedUrl: url };
  }
  if (/vk\.com\/video[-_]?\d|vkvideo\.ru\/video[-_]?\d/i.test(url)) {
    // Конвертируем ссылку на страницу в embed
    const m = url.match(/video(-?\d+)_(\d+)/);
    if (m) return { embedUrl: `https://vk.com/video_ext.php?oid=${m[1]}&id=${m[2]}&hd=2` };
  }

  // Rutube — форматы:
  //   https://rutube.ru/video/HASH/
  //   https://rutube.ru/play/embed/HASH
  if (/rutube\.ru/i.test(url)) {
    const embedMatch = url.match(/rutube\.ru\/(?:video|play\/embed)\/([a-f0-9]+)/i);
    if (embedMatch) return { embedUrl: `https://rutube.ru/play/embed/${embedMatch[1]}` };
  }

  return null; // не embed
}

// Бейджи для типов файлов
function badgeLabel(path) {
  const ext = extOf(path);
  if (EXT_VIDEO.has(ext))        return { icon: '🎬', label: 'Видео' };
  if (EXT_PPTX.has(ext))        return { icon: '📊', label: 'Презентация' };
  if (EXT_PDF.has(ext))         return { icon: '📄', label: 'PDF' };
  if (EXT_IMAGE.has(ext))       return { icon: '🖼️',  label: 'Фото' };
  if (EXT_TEXT.has(ext))        return { icon: '📝', label: 'Текст' };
  if (/vkvideo\.ru|vk\.com\/video|rutube\.ru/i.test(path)) return { icon: '🎬', label: 'Видео' };
  return { icon: '📁', label: ext.toUpperCase() };
}

// ── Боковая панель ────────────────────────────────────────────
function openSidebar(regionId) {
  // Снять выделение с предыдущего
  if (activeRegion) {
    const prev = document.getElementById(activeRegion);
    if (prev) prev.classList.remove('active');
  }

  activeRegion = regionId;
  const el = document.getElementById(regionId);
  if (el) el.classList.add('active');

  const data  = CONFIG.regions[regionId];
  const name  = data ? data.name : (el ? el.getAttribute('data-name') : regionId);
  const files = (data && data.files) ? data.files : [];
  const desc  = (data && data.description) ? data.description : '';

  document.getElementById('sidebarTitle').textContent = name;

  // Картинка
  const imageEl = document.getElementById('sidebarImage');
  if (imageEl) {
    imageEl.innerHTML = '';
    if (data && data.image) {
      const img = document.createElement('img');
      img.src = data.image;
      img.alt = name;
      imageEl.appendChild(img);
    }
  }

  // Описание
  const descEl = document.getElementById('sidebarDescription');
  descEl.textContent = desc;

  // Список файлов (скрыт, если есть кнопка «Подробнее»)
  const list = document.getElementById('fileList');
  list.innerHTML = '';

  // Кнопка «Подробнее»
  const footer = document.getElementById('sidebarFooter');
  footer.innerHTML = '';

  if (files.length > 0) {
    const btn = document.createElement('button');
    btn.className = 'btn-detail';
    btn.innerHTML = 'Подробнее <span class="btn-arrow">→</span>';
    btn.onclick = () => openDetail(regionId);
    footer.appendChild(btn);
  } else {
    list.innerHTML = '<li class="empty-msg">Материалы не добавлены</li>';
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

// ── Детальная страница ────────────────────────────────────────
function openDetail(regionId) {
  const data  = CONFIG.regions[regionId];
  if (!data) return;

  const name  = data.name || regionId;
  const files = data.files || [];

  document.getElementById('detailTitle').textContent = name;

  // ─ Левая панель: видео / embed / изображение / файл ──────────
  const mediaInner = document.getElementById('detailMediaInner');
  mediaInner.innerHTML = '';

  // Ищем главный медиафайл: сначала embed/видео, потом картинку, потом документ
  const mediaFile = files.find(f => detectEmbed(f) || isVideo(f.path) || isImage(f.path))
                 || files.find(f => EXT_PPTX.has(extOf(f.path)))
                 || files.find(f => EXT_PDF.has(extOf(f.path)));

  if (mediaFile) {
    const embed = detectEmbed(mediaFile);
    if (embed) {
      // ── VK Видео / Rutube / любой embed → iframe ────────────
      const wrap = document.createElement('div');
      wrap.style.cssText = 'position:relative;width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:#000';

      const loadMsg = document.createElement('div');
      loadMsg.className = 'embed-loading';
      loadMsg.textContent = 'Загрузка видео…';
      wrap.appendChild(loadMsg);

      const iframe = document.createElement('iframe');
      iframe.src = embed.embedUrl;
      iframe.style.cssText = 'width:100%;height:100%;border:none;display:block';
      iframe.setAttribute('allowfullscreen', '');
      iframe.setAttribute('allow', 'autoplay; fullscreen');
      iframe.addEventListener('load', () => loadMsg.remove());
      wrap.appendChild(iframe);
      mediaInner.appendChild(wrap);
    } else if (isVideo(mediaFile.path)) {
      // ── Прямой mp4/webm (Cloudflare R2, CDN, локальный) ─────
      const video = document.createElement('video');
      video.src = mediaFile.path;
      video.controls = true;
      video.autoplay = false;
      video.style.cssText = 'width:100%;height:100%;object-fit:contain;background:#000';
      mediaInner.appendChild(video);
    } else if (isImage(mediaFile.path)) {
      const img = document.createElement('img');
      img.src = mediaFile.path;
      img.alt = mediaFile.name;
      mediaInner.appendChild(img);
    } else {
      // Презентация / PDF — заглушка с кнопкой открытия
      const ph = document.createElement('div');
      ph.className = 'media-placeholder';
      ph.innerHTML = `
        <div class="placeholder-icon">${fileIcon(mediaFile.path)}</div>
        <div class="placeholder-name">${mediaFile.name}</div>
        <div class="placeholder-hint">${extOf(mediaFile.path).toUpperCase()} — откройте в отдельном окне</div>
        <a class="btn-open-file" href="${mediaFile.path}" target="_blank">Открыть файл ↗</a>`;
      mediaInner.appendChild(ph);
    }
  } else {
    mediaInner.innerHTML = `
      <div class="no-media">
        <div class="no-media-icon">🗺️</div>
        <div>Медиафайлы не добавлены</div>
      </div>`;
  }

  // ─ Правая панель: текст ────────────────────────────────────
  const textContent = document.getElementById('detailTextContent');
  textContent.innerHTML = '';

  const h3 = document.createElement('h3');
  h3.textContent = name;
  textContent.appendChild(h3);

  const body = document.createElement('div');
  body.className = 'detail-text-body';

  if (data.text) {
    const paras = data.text.split('\n\n');
    const figs  = data.figures || [];
    paras.forEach((para, idx) => {
      if (para.trim()) {
        const p = document.createElement('p');
        p.className = 'detail-text-para';
        p.textContent = para.trim();
        body.appendChild(p);
      }
      const fig = figs.find(f => f.afterParagraph === idx);
      if (fig) {
        const figure = document.createElement('figure');
        figure.className = 'detail-figure';
        const img = document.createElement('img');
        img.src = fig.src;
        img.alt = fig.caption;
        const cap = document.createElement('figcaption');
        cap.textContent = fig.caption;
        figure.appendChild(img);
        figure.appendChild(cap);
        body.appendChild(figure);
      }
    });
    textContent.appendChild(body);
  } else {
    // Попробовать загрузить первый .txt файл
    const txtFile = files.find(f => isText(f.path));
    if (txtFile) {
      body.className += ' detail-text-loading';
      body.textContent = 'Загрузка…';
      textContent.appendChild(body);
      fetch(txtFile.path)
        .then(r => r.ok ? r.text() : Promise.reject(r.status))
        .then(t => { body.className = 'detail-text-body'; body.textContent = t; })
        .catch(() => { body.className = 'detail-text-body detail-text-loading'; body.textContent = 'Не удалось загрузить файл.'; });
    } else {
      body.className += ' detail-text-loading';
      body.textContent = 'Описание не добавлено.';
      textContent.appendChild(body);
    }
  }

  // ─ Дополнительные файлы (всё кроме главного медиа) ─────────
  const extraEl = document.getElementById('detailExtraFiles');
  extraEl.innerHTML = '';
  const extras = files.filter(f => f !== mediaFile && !isText(f.path));
  if (extras.length > 0) {
    const title = document.createElement('div');
    title.className = 'detail-extra-title';
    title.textContent = 'Дополнительные материалы';
    const ul = document.createElement('ul');
    ul.className = 'detail-extra-list';
    extras.forEach(f => {
      const ext = extOf(f.path);
      const li  = document.createElement('li');
      li.className = 'detail-extra-item';
      li.innerHTML = `
        <a href="${f.path}" target="_blank">
          <span class="file-icon">${fileIcon(f.path)}</span>
          <span class="file-name">${f.name}</span>
          <span class="file-ext">${ext}</span>
        </a>`;
      ul.appendChild(li);
    });
    extraEl.appendChild(title);
    extraEl.appendChild(ul);
  }

  // ─ Мини-карта региона (под плеером) ────────────────────────
  const regionInfo = document.getElementById('detailRegionInfo');
  buildRegionMiniMap(regionId, regionInfo);

  document.getElementById('detailOverlay').classList.add('open');
}

function closeDetail() {
  const overlay = document.getElementById('detailOverlay');
  overlay.classList.remove('open');
  // Остановить видео если играет
  const video = overlay.querySelector('video');
  if (video) { video.pause(); video.src = ''; }
}

// ── Подсчёт регионов с файлами ────────────────────────────────
function countLocations() {
  if (!CONFIG || !CONFIG.regions) return 0;
  return Object.values(CONFIG.regions).filter(r => r.files && r.files.length > 0).length;
}

function updateLocationBadge() {
  const count = countLocations();
  const el = document.getElementById('locationCount');
  if (!el) return;
  el.textContent = count > 0 ? `${count} локаций` : '';
  el.style.display = count > 0 ? '' : 'none';
}

// ── Перевод lat/lon → SVG координаты (та же проекция что в build_svg.py) ──
const SVG_X0    = 103,   SVG_Y0    = 103;
const SVG_PX_W  = 20326, SVG_PX_H  = 9667;
const LON0 = 20, LAT0 = 81, LON_RANGE = 170, LAT_RANGE = 40;
const VIEWBOX_W = 20955, VIEWBOX_H = 11530;

// Вычислить полный вид под текущий размер контейнера.
//
// _fullVbW инициализируется один раз (при первом вызове) по формуле xMidYMid meet —
// это даёт точно тот же начальный масштаб карты, что и в оригинале.
// После этого _fullVbW остаётся постоянным: ширина viewBox не меняется при ресайзе/
// фуллскрине → Россия одинакового размера в обычном и полноэкранном режиме.
// При изменении высоты контейнера адаптируется только vbH (видно больше/меньше
// карты сверху/снизу), vbX/vbY центрируются.
function computeFullViewBox() {
  const el = document.getElementById('svgContainer');
  const cW = el ? el.offsetWidth  : window.innerWidth;
  const cH = el ? el.offsetHeight : Math.max(window.innerHeight - 58, 1);

  // Ленивая инициализация _fullVbW: масштаб как при xMidYMid meet.
  if (!_fullVbW && cW > 0 && cH > 0) {
    const scale = Math.min(cW / VIEWBOX_W, cH / VIEWBOX_H);
    _fullVbW = Math.round(cW / scale);
  }
  const fvW = _fullVbW || VIEWBOX_W;  // fallback на случай cW=0 при ранней инициализации

  // vbH адаптируется к текущей высоте контейнера; vbW постоянен.
  const vbH = cW > 0 ? Math.round(fvW * (cH / cW)) : VIEWBOX_H;
  const vbX = Math.round((VIEWBOX_W - fvW) / 2);
  const vbY = Math.round((VIEWBOX_H - vbH) / 2);
  return { vbX, vbY, vbW: fvW, vbH };
}

// Применить полный вид (обновляет глобальные _vbX/Y/W/H и viewBox SVG).
function applyFullView() {
  const fv = computeFullViewBox();
  _vbX = fv.vbX; _vbY = fv.vbY; _vbW = fv.vbW; _vbH = fv.vbH;
  if (_svgEl) _svgEl.setAttribute('viewBox', `${_vbX} ${_vbY} ${_vbW} ${_vbH}`);
}

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

// ── Градусная сетка (параллели и меридианы) ───────────────────
// Рисуется отдельным SVG-оверлеем поверх карты — покрывает весь контейнер до краёв.
function buildGraticule(svgEl) {
  // Убрать старый оверлей если есть
  const old = document.getElementById('graticuleOverlay');
  if (old) old.remove();

  const container = document.getElementById('svgContainer');
  if (!container) return;

  // offsetWidth/Height могут быть 0 до первого лэйаута — берём из родителя
  const mapArea = container.parentElement;
  const W = (container.offsetWidth  || mapArea?.offsetWidth  || window.innerWidth);
  const H = (container.offsetHeight || mapArea?.offsetHeight || window.innerHeight);

  // Учитываем текущий viewBox (zoom/pan).
  // preserveAspectRatio="xMidYMid meet": контент вписывается по меньшей стороне.
  const scale = Math.min(W / _vbW, H / _vbH);
  const offX  = (W - _vbW * scale) / 2;
  const offY  = (H - _vbH * scale) / 2;

  // SVG-координата → пиксели экрана (с учётом pan/zoom)
  function toPx(svgX, svgY) {
    return [offX + (svgX - _vbX) * scale, offY + (svgY - _vbY) * scale];
  }

  // Оверлей — абсолютно позиционированный SVG на весь контейнер
  const ov = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  ov.id = 'graticuleOverlay';
  ov.setAttribute('viewBox', `0 0 ${W} ${H}`);
  ov.style.cssText = [
    'position:absolute', 'top:0', 'left:0',
    'width:100%', 'height:100%',
    'pointer-events:none', 'overflow:visible',
    'z-index:10'
  ].join(';');

  const STROKE_W   = 1.5;
  const STROKE_CLR = '#5577aa';
  const STROKE_OPA = '0.5';
  const DASH       = '7,5';
  const FONT_SZ    = 12;
  const FONT_CLR   = '#33557a';
  const FONT_OPA   = '0.9';
  const PAD        = 4;

  const addLine = (x1, y1, x2, y2) => {
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    el.setAttribute('x1', x1); el.setAttribute('y1', y1);
    el.setAttribute('x2', x2); el.setAttribute('y2', y2);
    el.setAttribute('stroke',           STROKE_CLR);
    el.setAttribute('stroke-width',     STROKE_W);
    el.setAttribute('stroke-dasharray', DASH);
    el.setAttribute('opacity',          STROKE_OPA);
    ov.appendChild(el);
  };

  const addText = (x, y, txt, anchor = 'start') => {
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    el.setAttribute('x', x); el.setAttribute('y', y);
    el.setAttribute('font-size',   FONT_SZ);
    el.setAttribute('font-family', 'Arial, sans-serif');
    el.setAttribute('fill',        FONT_CLR);
    el.setAttribute('opacity',     FONT_OPA);
    el.setAttribute('text-anchor', anchor);
    el.textContent = txt;
    ov.appendChild(el);
  };

  const MARGIN = 16;  // отступ подписей от края экрана

  // ── Параллели каждые 10° — подписи слева И справа ───────────
  for (let lat = 40; lat <= 80; lat += 10) {
    const { y: svgY } = latLonToSvg(lat, LON0);
    const [, py] = toPx(0, svgY);
    if (py < FONT_SZ || py > H - 2) continue;
    addLine(0, py, W, py);
    // Левая подпись
    addText(MARGIN, py - 3, lat + '°', 'start');
    // Правая подпись
    addText(W - MARGIN, py - 3, lat + '°', 'end');
  }

  // ── Меридианы каждые 20° — подписи сверху И снизу ──────────
  for (let lon = 20; lon <= 180; lon += 20) {
    if (lon < LON0 || lon > LON0 + LON_RANGE) continue;
    const { x: svgX } = latLonToSvg(LAT0, lon);
    const [px] = toPx(svgX, 0);
    if (px < FONT_SZ * 2 || px > W - FONT_SZ * 2) continue;
    addLine(px, 0, px, H);
    // Верхняя подпись
    addText(px, MARGIN + FONT_SZ, lon + '°', 'middle');
    // Нижняя подпись
    addText(px, H - MARGIN, lon + '°', 'middle');
  }

  // ── Линейный масштаб (в левом нижнем углу) ──────────────────
  // Реальное расстояние рассчитывается на широте 60°N (средняя широта России).
  // 1° долготы на 60°N = cos(60°) × 111.32 км = 55.66 км
  const KM_PER_DEG = Math.cos(60 * Math.PI / 180) * 111.32;
  // SVG-единиц на 1 км (на этой широте):
  const svgUnitsPerKm = (SVG_PX_W / LON_RANGE) / KM_PER_DEG;
  // Пикселей оверлея на 1 км:
  const pxPerKm = svgUnitsPerKm * scale;

  // Выбираем длину линейки автоматически под текущий зум.
  // Целевая ширина бара ~150 пикселей; подбираем красивое число км.
  const TARGET_PX = 150;
  const rawKm = TARGET_PX / pxPerKm;
  const NICE = [10,20,50,100,150,200,250,500,750,1000,1500,2000,2500,5000,7500,10000];
  const BAR_KM = NICE.find(n => n * pxPerKm >= TARGET_PX * 0.7) || NICE[NICE.length - 1];
  const barLen = BAR_KM * pxPerKm;

  const bx   = W - MARGIN - 30 - barLen;
  const by   = H - MARGIN - 28;
  const tickH = 6;

  const mkLine = (x1, y1, x2, y2, w = 1.8, clr = '#2c3e2d') => {
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    el.setAttribute('x1', x1); el.setAttribute('y1', y1);
    el.setAttribute('x2', x2); el.setAttribute('y2', y2);
    el.setAttribute('stroke', clr); el.setAttribute('stroke-width', w);
    ov.appendChild(el);
  };
  const mkTxt = (x, y, txt, anchor = 'middle', sz = 10) => {
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    el.setAttribute('x', x); el.setAttribute('y', y);
    el.setAttribute('font-size', sz); el.setAttribute('font-family', 'Arial, sans-serif');
    el.setAttribute('fill', '#1a2e1a'); el.setAttribute('text-anchor', anchor);
    el.textContent = txt; ov.appendChild(el);
  };

  // Фон-подложка
  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  bg.setAttribute('x', bx - 8);   bg.setAttribute('y', by - 18);
  bg.setAttribute('width', barLen + 52); bg.setAttribute('height', 38);
  bg.setAttribute('rx', 4);       bg.setAttribute('fill', 'rgba(255,255,255,0.82)');
  ov.appendChild(bg);

  // Деления: 0, BAR_KM/4, BAR_KM/2, BAR_KM
  [0, 0.25, 0.5, 1].forEach(f => {
    const km  = Math.round(BAR_KM * f);
    const x   = bx + km * pxPerKm;
    mkLine(x, by - tickH / 2, x, by + tickH);
    mkTxt(x, by - tickH / 2 - 2, km === 0 ? '0' : km >= 1000 ? (km/1000) + ' тыс. км' : km + ' км');
  });
  mkLine(bx, by, bx + barLen, by, 1.8);

  // Чёрно-белые блоки
  [0, 0.25, 0.5, 0.75].forEach((f, i) => {
    const rx = bx + BAR_KM * f * pxPerKm;
    const rw = BAR_KM * 0.25 * pxPerKm;
    const rb = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rb.setAttribute('x', rx); rb.setAttribute('y', by);
    rb.setAttribute('width', rw); rb.setAttribute('height', tickH / 2);
    rb.setAttribute('fill', i % 2 === 0 ? '#2c3e2d' : 'white');
    rb.setAttribute('stroke', '#2c3e2d'); rb.setAttribute('stroke-width', '0.5');
    ov.appendChild(rb);
  });

  mkTxt(bx + barLen / 2, by + tickH + 10, 'Масштаб (на 60° с.ш.)', 'middle', 9);

  container.appendChild(ov);
}

// ── Мини-карта региона (для детальной страницы) ───────────────
function buildRegionMiniMap(regionId, container) {
  if (!container) return;

  const svgEl = document.querySelector('#svgContainer svg');
  if (!svgEl) { container.innerHTML = ''; return; }

  // Используем displayRegion из конфига если задан (напр. для Москвы → RU-MOS)
  const data         = CONFIG.regions[regionId] || {};
  const displayId    = data.displayRegion || regionId;
  const regionPath   = svgEl.querySelector('#' + displayId);
  if (!regionPath) { container.innerHTML = ''; return; }

  // Квадратный viewBox — все регионы выглядят одного размера
  const bbox    = regionPath.getBBox();
  const size    = Math.max(bbox.width, bbox.height);
  const pad     = size * 0.06 + 18;
  const total   = size + pad * 2;
  const cx      = bbox.x + bbox.width  / 2;
  const cy      = bbox.y + bbox.height / 2;
  const vbX     = cx - total / 2;
  const vbY     = cy - total / 2;
  const vbW     = total;
  const vbH     = total;

  const ns = 'http://www.w3.org/2000/svg';

  const mini = document.createElementNS(ns, 'svg');
  mini.setAttribute('viewBox', `${vbX} ${vbY} ${vbW} ${vbH}`);
  mini.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  mini.style.cssText = 'display:block;';

  // ── Форма региона — оригинальный цвет, тонкая тёмная граница ─
  const shape = regionPath.cloneNode(false);
  shape.removeAttribute('class');
  const st        = regionPath.getAttribute('style') || '';
  const fillMatch = st.match(/fill\s*:\s*([^;]+)/);
  const origFill  = fillMatch ? fillMatch[1].trim() : '#7ab648';
  shape.setAttribute('style',
    `fill:${origFill};stroke:rgba(0,0,0,0.45);stroke-width:5;`);
  mini.appendChild(shape);

  // ── Подпись региона ───────────────────────────────────────────
  const regionName = regionPath.getAttribute('data-name')
    || (CONFIG.regions[displayId] && CONFIG.regions[displayId].name)
    || '';

  const label = document.createElement('div');
  label.className = 'minimap-label';
  const span = document.createElement('span');
  span.textContent = regionName;
  label.appendChild(span);

  container.innerHTML = '';
  container.appendChild(mini);
  if (regionName) container.appendChild(label);
}

// ── Тултип маркера ────────────────────────────────────────────
function showMarkerTooltip(regionId, svgX, svgY) {
  const data = CONFIG.regions[regionId];
  const tooltip = document.getElementById('mapTooltip');
  if (!tooltip || !data) return;

  tooltip.querySelector('.tooltip-name').textContent = data.name || regionId;
  tooltip.querySelector('.tooltip-desc').textContent = (data.description || '').replace(/\n\n/g, ' ');

  const img = tooltip.querySelector('.tooltip-img');
  img.src = data.tooltipImage || '';

  // SVG → экранные координаты
  const container = document.getElementById('svgContainer');
  const rect = container.getBoundingClientRect();
  const sc   = Math.min(rect.width / _vbW, rect.height / _vbH);
  const offX = (rect.width  - _vbW * sc) / 2;
  const offY = (rect.height - _vbH * sc) / 2;
  const sx   = rect.left + offX + (svgX - _vbX) * sc;
  const sy   = rect.top  + offY + (svgY - _vbY) * sc;

  tooltip.style.display = 'block';
  const tw = tooltip.offsetWidth;
  const th = tooltip.offsetHeight;

  let left = sx - tw / 2;
  let top  = sy - th - 14;
  left = Math.max(8, Math.min(window.innerWidth - tw - 8, left));
  top  = Math.max(8, top);

  tooltip.style.left = left + 'px';
  tooltip.style.top  = top  + 'px';
}

function hideMarkerTooltip() {
  const el = document.getElementById('mapTooltip');
  if (el) el.style.display = 'none';
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

  const R  = 58;   // радиус кружка (~4px на экране)
  const R2 = 92;   // радиус белого кольца (~7px, всегда видимо)

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

    g.addEventListener('mouseenter', () => showMarkerTooltip(id, x, y));
    g.addEventListener('mouseleave', hideMarkerTooltip);
    g.addEventListener('click', e => {
      e.stopPropagation();
      hideMarkerTooltip();
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

// ── Zoom / Pan ────────────────────────────────────────────────
function bindZoomPan(svgEl, container) {
  _svgEl = svgEl;

  // ── Два уровня обновления ─────────────────────────────────────
  // applyViewBox — только атрибут viewBox, мгновенно (~0.1 мс)
  // applyView    — viewBox + перестройка сетки, вызывать только после окончания жеста
  function applyViewBox() {
    svgEl.setAttribute('viewBox', `${_vbX} ${_vbY} ${_vbW} ${_vbH}`);
  }
  function applyView() {
    applyViewBox();
    buildGraticule(svgEl);
  }

  // Конвертировать клиентские координаты в SVG-пространство
  // rect передаём снаружи чтобы не вызывать getBoundingClientRect лишний раз
  function clientToSvg(clientX, clientY, rect) {
    const sc   = Math.min(rect.width / _vbW, rect.height / _vbH);
    const offX = (rect.width  - _vbW * sc) / 2;
    const offY = (rect.height - _vbH * sc) / 2;
    return {
      x: _vbX + (clientX - rect.left - offX) / sc,
      y: _vbY + (clientY - rect.top  - offY) / sc,
    };
  }

  function clampView() {
    // При полном масштабе — перетаскивание отключено; применяем полный вид.
    const fvW = computeFullViewBox().vbW;
    if (_vbW >= fvW) {
      applyFullView();
      return;
    }
    // При зуме: небольшой запас за левый/верхний край (для Калининграда,
    // западных регионов). Справа/снизу запас не нужен — там уже есть поле.
    const padX = Math.min(400, _vbW * 0.10);
    const padY = Math.min(200, _vbH * 0.10);
    _vbX = Math.max(-padX, Math.min(VIEWBOX_W - _vbW + padX, _vbX));
    _vbY = Math.max(-padY, Math.min(VIEWBOX_H - _vbH + padY, _vbY));
  }

  // ── Колесо мыши: зум ─────────────────────────────────────────
  // Во время скролла обновляем только viewBox; сетку перестраиваем
  // один раз через 150 мс после последнего события колеса.
  let _wheelTimer = null;

  container.addEventListener('wheel', e => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 0.8 : 1.25;
    const rect   = container.getBoundingClientRect();
    const { x: mx, y: my } = clientToSvg(e.clientX, e.clientY, rect);

    const fvW  = computeFullViewBox().vbW;
    const newW = Math.min(fvW, Math.max(fvW * 0.05, _vbW * factor));
    const newH = newW * (VIEWBOX_H / VIEWBOX_W);
    const r    = newW / _vbW;

    _vbX = mx - (mx - _vbX) * r;
    _vbY = my - (my - _vbY) * r;
    _vbW = newW;
    _vbH = newH;
    clampView();
    applyViewBox();   // ← только атрибут, без сетки

    clearTimeout(_wheelTimer);
    _wheelTimer = setTimeout(() => buildGraticule(svgEl), 150);
  }, { passive: false });

  // ── Перетаскивание мышью ──────────────────────────────────────
  // Ключевые оптимизации:
  //   1. scale вычисляется один раз на mousedown (не меняется во время drag)
  //   2. viewBox обновляется через requestAnimationFrame — не чаще 60 fps
  //   3. getBoundingClientRect вызывается один раз на mousedown
  //   4. buildGraticule вызывается один раз на mouseup
  let dragging    = false;
  let didDrag     = false;
  let _dragVbX0   = 0, _dragVbY0   = 0;   // viewBox в момент начала drag
  let _dragCX0    = 0, _dragCY0    = 0;   // курсор в начале drag (client px)
  let _dragScale  = 1;                     // px → SVG-единицы (константа для всего drag)
  let _rafPending = false;

  container.addEventListener('mousedown', e => {
    if (e.button !== 0) return;
    dragging   = true;
    didDrag    = false;
    _dragVbX0  = _vbX;
    _dragVbY0  = _vbY;
    _dragCX0   = e.clientX;
    _dragCY0   = e.clientY;
    // scale не изменится пока не начнётся zoom — вычисляем один раз
    const rect = container.getBoundingClientRect();
    _dragScale = Math.min(rect.width / _vbW, rect.height / _vbH);
    container.style.cursor = 'grabbing';
    e.preventDefault();
  });

  window.addEventListener('mousemove', e => {
    if (!dragging) return;
    const dx = e.clientX - _dragCX0;
    const dy = e.clientY - _dragCY0;
    _vbX = _dragVbX0 - dx / _dragScale;
    _vbY = _dragVbY0 - dy / _dragScale;
    clampView();
    // Порог 5px: микро-дрожание мыши при клике не считается drag-ом
    if (Math.hypot(dx, dy) > 5) didDrag = true;
    // Один DOM-апдейт за кадр — лишние mousemove пропускаем
    if (!_rafPending) {
      _rafPending = true;
      requestAnimationFrame(() => {
        applyViewBox();
        _rafPending = false;
      });
    }
  });

  window.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    container.style.cursor = 'grab';
    if (didDrag) buildGraticule(svgEl);
  });

  // ── Двойной клик: сброс вида ─────────────────────────────────
  container.addEventListener('dblclick', e => {
    if (e.target.closest('path[id^="RU-"]')) return;
    applyFullView();
    buildGraticule(svgEl);
  });

  // Предотвратить клик по карте после перетаскивания
  container.addEventListener('click', e => {
    if (didDrag) { e.stopPropagation(); didDrag = false; }
  }, true);

  container.style.cursor = 'grab';
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

    // Сбрасываем _fullVbW — пересчитается под актуальный контейнер при первом applyFullView()
    _fullVbW = 0;
    // Сбрасываем viewBox в исходное состояние при каждой загрузке
    applyFullView();

    buildBackground(svgEl);
    bindRegionClicks(svgEl);
    buildMarkers(svgEl);
    bindZoomPan(svgEl, container);

    // Сетку строим после первого лэйаута
    requestAnimationFrame(() => buildGraticule(svgEl));

    // Пересчитываем сетку при изменении размера карты (открытие/закрытие панели)
    if (_graticuleObserver) _graticuleObserver.disconnect();
    _graticuleObserver = new ResizeObserver(() => {
      if (_vbW >= computeFullViewBox().vbW) applyFullView();
      buildGraticule(svgEl);
    });
    _graticuleObserver.observe(container);

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
  updateLocationBadge();
  loadSVG();

  document.getElementById('closeBtn').addEventListener('click', e => {
    e.stopPropagation();
    closeSidebar();
  });

  document.getElementById('detailBackBtn').addEventListener('click', closeDetail);

  // Кнопка «Вся карта» — сброс вида
  document.getElementById('resetViewBtn').addEventListener('click', () => {
    applyFullView();
    if (_svgEl) buildGraticule(_svgEl);
    closeSidebar();
  });

  // Кнопка полноэкранного режима
  const fsBtn = document.getElementById('fullscreenBtn');
  fsBtn.addEventListener('click', () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  });

  // Меняем иконку кнопки в зависимости от режима
  document.addEventListener('fullscreenchange', () => {
    const isFs = !!document.fullscreenElement;
    fsBtn.title = isFs ? 'Выйти из полноэкранного режима' : 'Полноэкранный режим';
    fsBtn.querySelector('svg').innerHTML = isFs
      ? `<path d="M5 1v3a1 1 0 0 1-1 1H1M9 1v3a1 1 0 0 0 1 1h3M1 9h3a1 1 0 0 1 1 1v3M13 9h-3a1 1 0 0 0-1 1v3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>`
      : `<path d="M1 5V2a1 1 0 0 1 1-1h3M9 1h3a1 1 0 0 1 1 1v3M13 9v3a1 1 0 0 1-1 1H9M5 13H2a1 1 0 0 1-1-1V9" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>`;
  });
}

document.addEventListener('DOMContentLoaded', init);
