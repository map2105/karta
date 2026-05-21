# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
build_svg.py
Generirует russia.svg s id-atributami na kazhdom regione.
Rezultat: russia_new.svg (pereimenuyte v russia.svg ili --replace)
"""
import sys, io
# Принудительно UTF-8 на Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
import os
import urllib.request

# ── GeoJSON-источники ─────────────────────────────────────────────────────
# Основной (83 региона РФ)
GEOJSON_URLS = [
    "https://raw.githubusercontent.com/subpath/russia-regions-geojson/main/russia.geojson",
    "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/russia.geojson",
]

# Дополнительный — Украина, для Крыма/ДНР/ЛНР/Запорожья/Херсона
UKRAINE_GEOJSON_URLS = [
    # GADM 4.1 — официальные границы, включает Крым (NAME_1)
    "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_UKR_1.json",
    # Запасные
    "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/ukraine.geojson",
]

# Маппинг украинских/крымских названий → ISO российских регионов
# (используем полные границы областей)
UA_NAME_TO_RU_ISO = {
    # ── GADM 4.1 (NAME_1, английский) ────────────────────────────────────
    "Crimea":                              "RU-CR",
    "Sevastopol":                          "RU-SEV",
    "Sevastopol'":                         "RU-SEV",
    "Donetsk":                             "RU-DN",
    "Donets'k":                            "RU-DN",
    "Luhansk":                             "RU-LU",
    "Luhans'k":                            "RU-LU",
    "Zaporizhzhya":                        "RU-ZP",
    "Zaporizhzhia":                        "RU-ZP",
    "Zaporizhia":                          "RU-ZP",   # GADM 4.1
    "Kherson":                             "RU-KS",
    # ── Украинские названия (кириллица) ───────────────────────────────────
    "Автономна Республіка Крим":          "RU-CR",
    "Крим":                                "RU-CR",
    "Autonomous Republic of Crimea":       "RU-CR",
    "Republic of Crimea":                  "RU-CR",
    "Севастополь":                         "RU-SEV",
    "місто Севастополь":                   "RU-SEV",
    "Донецька область":                    "RU-DN",
    "Донецька":                            "RU-DN",
    "Donetsk Oblast":                      "RU-DN",
    "Луганська область":                   "RU-LU",
    "Луганська":                           "RU-LU",
    "Luhansk Oblast":                      "RU-LU",
    "Lugansk":                             "RU-LU",
    "Запорізька область":                  "RU-ZP",
    "Запорізька":                          "RU-ZP",
    "Zaporizhzhia Oblast":                 "RU-ZP",
    "Zaporizhska":                         "RU-ZP",
    "Херсонська область":                  "RU-KS",
    "Херсонська":                          "RU-KS",
    "Kherson Oblast":                      "RU-KS",
    "Khersonska":                          "RU-KS",
}

# 6 ISO-кодов которые берём из украинского GeoJSON
MISSING_FROM_RUSSIA = {"RU-CR", "RU-SEV", "RU-DN", "RU-LU", "RU-ZP", "RU-KS"}

# ── Запасные координаты для 6 регионов (если GeoJSON не найден) ────────────
# Формат: [(lon, lat), ...] — приближённые границы по географическим данным
FALLBACK_COORDS = {
    # Республика Крым — полуостров в Чёрном море
    "RU-CR": [
        (32.5, 46.1), (33.5, 46.2), (34.5, 46.1), (35.1, 45.9),
        (35.5, 45.7), (36.3, 45.5), (36.6, 45.3), (36.3, 45.0),
        (36.0, 44.8), (35.3, 44.6), (34.5, 44.5), (34.0, 44.4),
        (33.5, 44.4), (33.1, 44.5), (32.7, 44.8), (32.5, 45.2),
        (32.5, 45.7), (32.5, 46.1),
    ],
    # Севастополь — город на юго-западе Крыма
    "RU-SEV": [
        (33.3, 44.8), (33.6, 44.85), (33.95, 44.7), (33.9, 44.45),
        (33.6, 44.38), (33.3, 44.45), (33.2, 44.6), (33.3, 44.8),
    ],
    # Донецкая Народная Республика
    "RU-DN": [
        (36.8, 49.2), (37.5, 49.3), (38.1, 49.3), (38.5, 49.1),
        (39.0, 49.0), (39.4, 48.7), (39.7, 48.2), (39.3, 47.85),
        (38.7, 47.6), (38.2, 47.5), (37.5, 47.8), (37.0, 48.05),
        (36.8, 48.5), (36.8, 49.2),
    ],
    # Луганская Народная Республика
    "RU-LU": [
        (38.3, 49.3), (38.6, 49.5), (38.9, 50.0), (39.3, 50.2),
        (39.8, 50.05), (40.2, 49.6), (40.0, 49.1), (39.5, 48.85),
        (39.0, 49.0), (38.5, 49.1), (38.3, 49.3),
    ],
    # Запорожская область
    "RU-ZP": [
        (34.5, 48.35), (35.2, 48.5), (36.0, 48.5), (36.6, 48.2),
        (36.5, 47.6), (36.1, 47.1), (35.5, 46.6), (34.9, 46.5),
        (34.5, 46.8), (34.5, 47.5), (34.5, 48.35),
    ],
    # Херсонская область
    "RU-KS": [
        (32.5, 47.55), (33.5, 47.75), (34.5, 47.55), (34.5, 46.85),
        (34.0, 46.4),  (33.5, 46.2),  (33.0, 46.05), (32.5, 46.1),
        (32.3, 46.5),  (32.4, 47.0),  (32.5, 47.55),
    ],
}

# ── Страны мира (для соседних территорий) ─────────────────────────────────
# Порядок: сначала более детальные (50m), потом запасные грубые (110m)
WORLD_GEOJSON_URLS = [
    # Natural Earth 50m — в 2.2x детальнее чем 110m, ~3 MB
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson",
    # Natural Earth 110m — запасной, ~400 KB
    "https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson",
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson",
]

SEA_COLOR     = "#b8d4e8"   # цвет моря (фон SVG)
# Соседи — очень светлая почти-серая штриховка, чтобы Россия выделялась
NEIGHBOR_FILL = "#e8e5dc"   # светлее и нейтральнее
NEIGHBOR_LINE = "#cec9bc"   # очень слабые линии

# ── Ручные позиции подписей стран (lon, lat) — для точного размещения ─────
# Если страна есть здесь — используем эту точку, иначе вычисляем автоматически
MANUAL_LABEL_POS = {
    "Норвегия":          ( 20.0, 67.5),
    "Швеция":            ( 17.0, 63.0),
    "Финляндия":         ( 26.5, 63.0),
    "Эстония":           ( 25.0, 58.7),
    "Латвия":            ( 25.0, 57.0),
    "Литва":             ( 24.0, 55.7),
    "Польша":            ( 20.5, 52.0),
    "Беларусь":          ( 28.0, 53.5),
    "Украина":           ( 31.5, 49.0),
    "Молдова":           ( 28.5, 47.2),
    "Румыния":           ( 25.0, 45.5),
    "Болгария":          ( 25.0, 42.7),
    "Турция":            ( 35.5, 39.5),
    "Грузия":            ( 43.5, 42.0),
    "Азербайджан":       ( 47.5, 40.5),
    "Армения":           ( 44.5, 40.2),
    "Иран":              ( 53.0, 33.0),
    "Афганистан":        ( 65.0, 33.0),
    "Казахстан":         ( 67.0, 48.0),
    "Узбекистан":        ( 63.0, 41.5),
    "Туркменистан":      ( 58.5, 39.5),
    "Таджикистан":       ( 71.0, 38.5),
    "Кыргызстан":        ( 74.5, 41.5),
    "Монголия":          (103.0, 46.5),
    "Китай":             (103.0, 38.0),
    "Сев. Корея":        (127.0, 40.5),
    "Япония":            (137.0, 37.0),
    "США":               (195.0, 64.5),
    "Норвегия":          ( 14.0, 65.0),
    "Дания":             ( 10.0, 56.0),
    "Германия":          ( 10.5, 51.0),
    "Чехия":             ( 15.5, 49.8),
    "Австрия":           ( 14.5, 47.5),
    "Венгрия":           ( 19.0, 47.0),
    "Словакия":          ( 19.5, 48.7),
    "Сербия":            ( 21.0, 44.0),
    "Греция":            ( 22.0, 39.5),
}

# ── Перевод названий стран на русский (для подписей) ──────────────────────
COUNTRY_NAMES_RU = {
    "Norway":                   "Норвегия",
    "Sweden":                   "Швеция",
    "Finland":                  "Финляндия",
    "Estonia":                  "Эстония",
    "Latvia":                   "Латвия",
    "Lithuania":                "Литва",
    "Poland":                   "Польша",
    "Belarus":                  "Беларусь",
    "Ukraine":                  "Украина",
    "Moldova":                  "Молдова",
    "Romania":                  "Румыния",
    "Bulgaria":                 "Болгария",
    "Turkey":                   "Турция",
    "Türkiye":                  "Турция",
    "Georgia":                  "Грузия",
    "Azerbaijan":               "Азербайджан",
    "Armenia":                  "Армения",
    "Iran":                     "Иран",
    "Afghanistan":              "Афганистан",
    "Pakistan":                 "Пакистан",
    "Kazakhstan":               "Казахстан",
    "Uzbekistan":               "Узбекистан",
    "Turkmenistan":             "Туркменистан",
    "Tajikistan":               "Таджикистан",
    "Kyrgyzstan":               "Кыргызстан",
    "Mongolia":                 "Монголия",
    "China":                    "Китай",
    "North Korea":              "Сев. Корея",
    "South Korea":              "Юж. Корея",
    "Japan":                    "Япония",
    "United States of America": "США",
    "United States":            "США",
    "Iceland":                  "Исландия",
    "Greenland":                "Гренландия",
    "Denmark":                  "Дания",
    "Germany":                  "Германия",
    "Hungary":                  "Венгрия",
    "Slovakia":                 "Словакия",
    "Czechia":                  "Чехия",
    "Czech Republic":           "Чехия",
    "Austria":                  "Австрия",
    "Switzerland":              "Швейцария",
    "France":                   "Франция",
    "Italy":                    "Италия",
    "Greece":                   "Греция",
    "Serbia":                   "Сербия",
    "Iraq":                     "Ирак",
    "Syria":                    "Сирия",
    "Israel":                   "Израиль",
    "Saudi Arabia":             "Саудовская Аравия",
    "India":                    "Индия",
    "Mongolia":                 "Монголия",
    "Taiwan":                   "Тайвань",
    "Philippines":              "Филиппины",
    "Indonesia":                "Индонезия",
    "Vietnam":                  "Вьетнам",
    "Myanmar":                  "Мьянма",
}

# Подписи морей/океанов: (lon, lat, текст, размер-шрифта, угол_градусы)
# Координаты = центр водного пространства (чтобы метка гарантированно в воде).
# Угол: 0=горизонт, отрицательный=наклон влево-вверх (следует оси моря).
# Масштаб при 1500px: 1 SVG unit ≈ 0.072px → font 240 ≈ 17px
SEA_LABEL_DEFS = [
    # ── Арктика (слева направо) ────────────────────────────────────────────
    # Северный Ледовитый океан:
    #   text-anchor=middle → текст тянется ±13° lon от центра при size≈210.
    #   Восточный берег Северной Земли ≈ lon 105-107 (lat 80).
    #   Западный берег Новосибирских о-вов ≈ lon 133-137 (lat 73-76, выше lat 80 их нет).
    #   lon=120, lat=80.5 → левый край ≈ lon 107 (у берега Северной Земли), правый ≈ lon 133.
    #   Делаем lon=125 чтобы левый край ≈ lon 112, гарантированно в воде.
    (125.0, 80.5, "Северный Ледовитый океан",  200,   0),

    # Баренцево море:
    #   Новая Земля (западный берег) ≈ lon 50-57.  Норвегия ≈ lon 28-32.
    #   lon=40, lat=74 — открытая вода.  ✓
    ( 40.0, 74.0, "Баренцево море",            165,   0),

    # Карское море:
    #   Новая Земля (восточный берег): на lat=76 ≈ lon 65-68.
    #   Ямал (западный берег): на lat=76 заканчивается примерно lon 68-70.
    #   Северная Земля (западный берег): на lat=76 ≈ lon 85-87.
    #   Открытое Карское море на lat=76: от lon≈69 до lon≈85. Центр ≈ lon 77.
    #   При size=155 текст тянется ≈ ±5° lon → lon 77±5 = 72–82. В воде. ✓
    ( 77.0, 76.0, "Карское море",              155,   0),

    # Море Лаптевых:
    #   Северная Земля (восточный берег): на lat=77 ≈ lon 104-107.
    #   Котельный о-в (западный берег Новосибирских о-вов): lon≈137-138 (lat 75-76).
    #   На lat=77 открытое море между lon 107 и lon 137. Центр ≈ lon 122.
    (122.0, 77.0, "Море Лаптевых",             158,   0),

    # Восточно-Сибирское море:
    #   Новосибирские о-ва (восточный берег) ≈ lon 156-160 (lat 73-74).
    #   О.Врангеля (западный берег) ≈ lon 178 (lat 70.5-71.5).
    #   Открытое море на lat=72: lon 160-178. Центр ≈ lon 165. Size=142 → ±5°→ 160-170.  ✓
    (165.0, 72.0, "Восточно-Сибирское море",   142,   0),

    # Чукотское море:
    #   О.Врангеля: lon 178-182, lat 70.5-71.5 → берём lat=69.5 (ниже острова).
    #   Побережье Чукотки: на lon=168 — lat ≈ 65-67 → lat=69.5 выше берега.  ✓
    (168.0, 69.5, "Чукотское море",            140,   0),

    # ── Тихоокеанские ─────────────────────────────────────────────────────

    # Берингово море:
    #   Западный берег Камчатки на lat=59 ≈ lon 156-157.
    #   При lon=174, lat=58.5 — открытое Берингово море.  ✓
    (174.0, 58.5, "Берингово море",            162,  -8),

    # Охотское море:
    #   Сахалин (восточный берег) на lat=53.5 ≈ lon 143-144.
    #   Западный берег Камчатки на lat=53.5 ≈ lon 156-158.
    #   Центр: lon=150, lat=53.5 → между берегами.  ✓
    (150.0, 53.5, "Охотское море",             162,  -8),

    # Японское море:
    #   Берег Приморья на lat=43 ≈ lon 131.5-133.
    #   При lon=136, lat=42.5 — открытое море.  ✓
    (136.0, 42.5, "Японское море",             148, -15),

    # ── Западные / южные ──────────────────────────────────────────────────

    # Чёрное море:
    #   Южный берег Крыма ≈ lat 44.3-44.5. Берём lat=43 — ниже Крыма.  ✓
    ( 34.0, 43.0, "Чёрное море",               132,   0),

    # Каспийское море:
    #   Восточный берег (Казахстан) на lat=43 ≈ lon 52-52.5.
    #   Западный берег (Россия/Азербайджан) на lat=43 ≈ lon 50.
    #   При size=118, -8° поворот, центр lon=51, lat=42.5 — внутри акватории.  ✓
    ( 51.0, 42.5, "Каспийское море",           118,  -8),

    # Балтийское море (видна только восточная часть — Финский залив):
    #   Хельсинки lat=60.17, Таллин lat=59.43.
    #   Центр Финского залива по широте: lat≈59.75.
    #   При lon=26, lat=59.75 — чистая вода между финским и эстонским берегами.  ✓
    ( 26.0, 59.75, "Балтийское море",          108, -10),
]

# ── Параметры SVG (те же, что в map.js) ───────────────────────────────────
VIEWBOX_W  = 20955
VIEWBOX_H  = 11530
MARGIN_X   = 103      # отступ слева и справа
MARGIN_Y   = 103      # отступ сверху
SVG_PX_W   = 20326    # 103 + (lon-20)/170*20326
SVG_PX_H   =  9667    # 103 + (81-lat)/40*9667
LON0, LON1 = 20.0, 190.0   # западный/восточный край
LAT0, LAT1 = 81.0,  41.0   # северный/южный край

# ── Цветовая палитра (7 насыщенных цветов для регионов РФ) ────────────────
# Яркие, но не кислотные — хорошо выделяются на светло-серой штриховке соседей
PALETTE = [
    "#94cc52",  # яркий зелёный
    "#f0a82a",  # тёплый янтарь
    "#60b4e0",  # небесно-голубой
    "#e87070",  # коралловый
    "#b484d8",  # лавандово-фиолетовый
    "#50c888",  # изумрудный
    "#f5d038",  # ярко-жёлтый
]

# ── Маппинг русских названий → ISO 3166-2:RU ──────────────────────────────
NAME_TO_ISO = {
    # Республики
    "Республика Адыгея":                     "RU-AD",
    "Адыгея":                                "RU-AD",
    "Республика Алтай":                      "RU-AL",
    "Алтай":                                 "RU-AL",
    "Республика Башкортостан":               "RU-BA",
    "Башкортостан":                          "RU-BA",
    "Республика Бурятия":                    "RU-BU",
    "Бурятия":                               "RU-BU",
    "Республика Дагестан":                   "RU-DA",
    "Дагестан":                              "RU-DA",
    "Республика Ингушетия":                  "RU-IN",
    "Ингушетия":                             "RU-IN",
    "Кабардино-Балкарская Республика":       "RU-KB",
    "Кабардино-Балкария":                    "RU-KB",
    "Республика Калмыкия":                   "RU-KL",
    "Калмыкия":                              "RU-KL",
    "Карачаево-Черкесская Республика":       "RU-KC",
    "Карачаево-Черкесия":                    "RU-KC",
    "Республика Карелия":                    "RU-KR",
    "Карелия":                               "RU-KR",
    "Республика Коми":                       "RU-KO",
    "Коми":                                  "RU-KO",
    "Республика Крым":                       "RU-CR",
    "Крым":                                  "RU-CR",
    "Республика Марий Эл":                   "RU-ME",
    "Марий Эл":                              "RU-ME",
    "Республика Мордовия":                   "RU-MO",
    "Мордовия":                              "RU-MO",
    "Республика Саха (Якутия)":              "RU-SA",
    "Якутия":                                "RU-SA",
    "Саха":                                  "RU-SA",
    "Республика Северная Осетия — Алания":   "RU-SE",
    "Северная Осетия":                       "RU-SE",
    "Северная Осетия-Алания":               "RU-SE",
    "Республика Татарстан":                  "RU-TA",
    "Татарстан":                             "RU-TA",
    "Республика Тыва":                       "RU-TY",
    "Тыва":                                  "RU-TY",
    "Удмуртская Республика":                 "RU-UD",
    "Удмуртия":                              "RU-UD",
    "Республика Хакасия":                    "RU-KK",
    "Хакасия":                               "RU-KK",
    "Чеченская Республика":                  "RU-CE",
    "Чечня":                                 "RU-CE",
    "Чувашская Республика":                  "RU-CU",
    "Чувашия":                               "RU-CU",
    # Края
    "Алтайский край":                        "RU-ALT",
    "Забайкальский край":                    "RU-ZAB",
    "Камчатский край":                       "RU-KAM",
    "Краснодарский край":                    "RU-KDA",
    "Красноярский край":                     "RU-KYA",
    "Пермский край":                         "RU-PER",
    "Приморский край":                       "RU-PRI",
    "Ставропольский край":                   "RU-STA",
    "Хабаровский край":                      "RU-KHA",
    # Области
    "Амурская область":                      "RU-AMU",
    "Архангельская область":                 "RU-ARK",
    "Астраханская область":                  "RU-AST",
    "Белгородская область":                  "RU-BEL",
    "Брянская область":                      "RU-BRY",
    "Владимирская область":                  "RU-VLA",
    "Волгоградская область":                 "RU-VGG",
    "Вологодская область":                   "RU-VLG",
    "Воронежская область":                   "RU-VOR",
    "Еврейская автономная область":          "RU-YEV",
    "Ивановская область":                    "RU-IVA",
    "Иркутская область":                     "RU-IRK",
    "Калининградская область":               "RU-KGD",
    "Калужская область":                     "RU-KLU",
    "Кемеровская область":                   "RU-KEM",
    "Кировская область":                     "RU-KIR",
    "Костромская область":                   "RU-KOS",
    "Курганская область":                    "RU-KGN",
    "Курская область":                       "RU-KRS",
    "Ленинградская область":                 "RU-LEN",
    "Липецкая область":                      "RU-LIP",
    "Магаданская область":                   "RU-MAG",
    "Московская область":                    "RU-MOS",
    "Мурманская область":                    "RU-MUR",
    "Нижегородская область":                 "RU-NIZ",
    "Новгородская область":                  "RU-NGR",
    "Новосибирская область":                 "RU-NVS",
    "Омская область":                        "RU-OMS",
    "Оренбургская область":                  "RU-ORE",
    "Орловская область":                     "RU-ORL",
    "Пензенская область":                    "RU-PNZ",
    "Псковская область":                     "RU-PSK",
    "Ростовская область":                    "RU-ROS",
    "Рязанская область":                     "RU-RYA",
    "Самарская область":                     "RU-SAM",
    "Саратовская область":                   "RU-SAR",
    "Сахалинская область":                   "RU-SAK",
    "Свердловская область":                  "RU-SVE",
    "Смоленская область":                    "RU-SMO",
    "Тамбовская область":                    "RU-TAM",
    "Томская область":                       "RU-TOM",
    "Тульская область":                      "RU-TUL",
    "Тверская область":                      "RU-TVE",
    "Тюменская область":                     "RU-TYU",
    "Ульяновская область":                   "RU-ULY",
    "Челябинская область":                   "RU-CHE",
    "Ярославская область":                   "RU-YAR",
    # Города федерального значения
    "Москва":                                "RU-MOW",
    "Санкт-Петербург":                       "RU-SPE",
    "Севастополь":                           "RU-SEV",
    # Автономные округа
    "Ненецкий автономный округ":             "RU-NEN",
    "Чукотский автономный округ":            "RU-CHU",
    "Ханты-Мансийский автономный округ":     "RU-KHM",
    "Ханты-Мансийский АО":                  "RU-KHM",
    "Ямало-Ненецкий автономный округ":       "RU-YAN",
    "Ямало-Ненецкий АО":                    "RU-YAN",
    # Новые регионы (с 2022)
    "Донецкая Народная Республика":          "RU-DN",
    "ДНР":                                   "RU-DN",
    "Луганская Народная Республика":         "RU-LU",
    "ЛНР":                                   "RU-LU",
    "Запорожская область":                   "RU-ZP",
    "Херсонская область":                    "RU-KS",
}

# Английские варианты (на случай если GeoJSON на английском)
NAME_TO_ISO_EN = {
    "Republic of Adygea": "RU-AD",
    "Altai Republic": "RU-AL",
    "Altai Krai": "RU-ALT",
    "Amur Oblast": "RU-AMU",
    "Arkhangelsk Oblast": "RU-ARK",
    "Astrakhan Oblast": "RU-AST",
    "Republic of Bashkortostan": "RU-BA",
    "Belgorod Oblast": "RU-BEL",
    "Bryansk Oblast": "RU-BRY",
    "Republic of Buryatia": "RU-BU",
    "Chechen Republic": "RU-CE",
    "Chelyabinsk Oblast": "RU-CHE",
    "Chukotka Autonomous Okrug": "RU-CHU",
    "Chuvash Republic": "RU-CU",
    "Republic of Dagestan": "RU-DA",
    "Jewish Autonomous Oblast": "RU-YEV",
    "Zabaykalsky Krai": "RU-ZAB",
    "Ivanovo Oblast": "RU-IVA",
    "Republic of Ingushetia": "RU-IN",
    "Irkutsk Oblast": "RU-IRK",
    "Kabardino-Balkarian Republic": "RU-KB",
    "Kaliningrad Oblast": "RU-KGD",
    "Republic of Kalmykia": "RU-KL",
    "Kaluga Oblast": "RU-KLU",
    "Kamchatka Krai": "RU-KAM",
    "Karachay-Cherkess Republic": "RU-KC",
    "Republic of Karelia": "RU-KR",
    "Kemerovo Oblast": "RU-KEM",
    "Khabarovsk Krai": "RU-KHA",
    "Republic of Khakassia": "RU-KK",
    "Khanty-Mansi Autonomous Okrug": "RU-KHM",
    "Kirov Oblast": "RU-KIR",
    "Komi Republic": "RU-KO",
    "Kostroma Oblast": "RU-KOS",
    "Krasnodar Krai": "RU-KDA",
    "Krasnoyarsk Krai": "RU-KYA",
    "Kurgan Oblast": "RU-KGN",
    "Kursk Oblast": "RU-KRS",
    "Leningrad Oblast": "RU-LEN",
    "Lipetsk Oblast": "RU-LIP",
    "Magadan Oblast": "RU-MAG",
    "Mari El Republic": "RU-ME",
    "Republic of Mordovia": "RU-MO",
    "Moscow Oblast": "RU-MOS",
    "Moscow": "RU-MOW",
    "Murmansk Oblast": "RU-MUR",
    "Nenets Autonomous Okrug": "RU-NEN",
    "Nizhny Novgorod Oblast": "RU-NIZ",
    "Novgorod Oblast": "RU-NGR",
    "Novosibirsk Oblast": "RU-NVS",
    "Omsk Oblast": "RU-OMS",
    "Orenburg Oblast": "RU-ORE",
    "Oryol Oblast": "RU-ORL",
    "Penza Oblast": "RU-PNZ",
    "Perm Krai": "RU-PER",
    "Primorsky Krai": "RU-PRI",
    "Pskov Oblast": "RU-PSK",
    "Rostov Oblast": "RU-ROS",
    "Ryazan Oblast": "RU-RYA",
    "Sakhalin Oblast": "RU-SAK",
    "Samara Oblast": "RU-SAM",
    "Saratov Oblast": "RU-SAR",
    "Sakha Republic": "RU-SA",
    "Saint Petersburg": "RU-SPE",
    "Republic of North Ossetia–Alania": "RU-SE",
    "Smolensk Oblast": "RU-SMO",
    "Stavropol Krai": "RU-STA",
    "Sverdlovsk Oblast": "RU-SVE",
    "Tambov Oblast": "RU-TAM",
    "Republic of Tatarstan": "RU-TA",
    "Tomsk Oblast": "RU-TOM",
    "Tula Oblast": "RU-TUL",
    "Tuva Republic": "RU-TY",
    "Tver Oblast": "RU-TVE",
    "Tyumen Oblast": "RU-TYU",
    "Udmurt Republic": "RU-UD",
    "Ulyanovsk Oblast": "RU-ULY",
    "Vladimir Oblast": "RU-VLA",
    "Volgograd Oblast": "RU-VGG",
    "Vologda Oblast": "RU-VLG",
    "Voronezh Oblast": "RU-VOR",
    "Yamalo-Nenets Autonomous Okrug": "RU-YAN",
    "Yaroslavl Oblast": "RU-YAR",
    "Republic of Crimea": "RU-CR",
    "Crimea": "RU-CR",
    "Sevastopol": "RU-SEV",
}

# ── Перевод географических → SVG координаты ───────────────────────────────
def geo_to_svg(lon, lat):
    # Нормализуем долготу: -170° → 190° (для Чукотки)
    if lon < 0:
        lon += 360
    x = MARGIN_X + (lon - LON0) / (LON1 - LON0) * SVG_PX_W
    y = MARGIN_Y + (LAT0 - lat) / (LAT0 - LAT1) * SVG_PX_H
    return round(x, 1), round(y, 1)


# ── Упрощение ломаной (алгоритм Рамера-Дугласа-Пёкера) ────────────────────
def rdp(points, epsilon=1.5):
    """Удаляет лишние точки, сохраняя форму."""
    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = (dx*dx + dy*dy) ** 0.5
    if length == 0:
        return [start, end]
    max_dist, max_idx = 0, 0
    for i in range(1, len(points) - 1):
        px, py = points[i]
        dist = abs(dy*px - dx*py + end[0]*start[1] - end[1]*start[0]) / length
        if dist > max_dist:
            max_dist, max_idx = dist, i
    if max_dist > epsilon:
        left  = rdp(points[:max_idx+1], epsilon)
        right = rdp(points[max_idx:], epsilon)
        return left[:-1] + right
    return [start, end]


# ── Кольцо координат → строка SVG-пути ────────────────────────────────────
def ring_to_path(coords):
    # GeoJSON-кольца замкнуты (last == first) — убираем последнюю точку
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    pts = [geo_to_svg(c[0], c[1]) for c in coords]
    pts = rdp(pts, epsilon=2.0)
    if len(pts) < 3:
        return ""
    d = f"M {pts[0][0]},{pts[0][1]}"
    d += " L " + " ".join(f"{p[0]},{p[1]}" for p in pts[1:])
    d += " Z"
    return d


# ── GeoJSON геометрия → строка SVG-пути ───────────────────────────────────
def geometry_to_path(geometry):
    gtype = geometry["type"]
    coords = geometry["coordinates"]
    parts = []

    if gtype == "Polygon":
        for ring in coords:
            p = ring_to_path(ring)
            if p:
                parts.append(p)

    elif gtype == "MultiPolygon":
        for polygon in coords:
            for ring in polygon:
                p = ring_to_path(ring)
                if p:
                    parts.append(p)

    return " ".join(parts)


# ── GeoJSON геометрия → SVG-путь с настраиваемым epsilon ──────────────────
def geometry_to_path_eps(geometry, epsilon=3.0):
    """Как geometry_to_path, но с заданным epsilon (для мировых стран)."""
    gtype  = geometry["type"]
    coords = geometry["coordinates"]
    parts  = []

    def rtp(ring):
        if len(ring) > 1 and ring[0] == ring[-1]:
            ring = ring[:-1]
        pts = [geo_to_svg(c[0], c[1]) for c in ring]
        pts = rdp(pts, epsilon=epsilon)
        if len(pts) < 3:
            return ""
        d = f"M {pts[0][0]},{pts[0][1]}"
        d += " L " + " ".join(f"{p[0]},{p[1]}" for p in pts[1:])
        d += " Z"
        return d

    if gtype == "Polygon":
        for ring in coords:
            p = rtp(ring)
            if p: parts.append(p)
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                p = rtp(ring)
                if p: parts.append(p)
    return " ".join(parts)


def is_in_viewport(geometry):
    """True если геометрия хоть частично попадает в расширенный viewport карты."""
    lon_min, lon_max = LON0 - 5,  LON1 + 5
    lat_min, lat_max = LAT1 - 8,  LAT0 + 3

    def check(item):
        if not item:
            return False
        if isinstance(item[0], (int, float)):
            lon, lat = item[0], item[1]
            if lon < 0:
                lon += 360
            return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max
        return any(check(sub) for sub in item)

    return check(geometry.get("coordinates", []))


def compute_visible_center(geometry):
    """Возвращает (lon, lat) центра ВИДИМОЙ части геометрии.
    Берёт среднее всех координат, попадающих в расширенный viewport."""
    lon_min_vp = LON0 - 3
    lon_max_vp = LON1 + 3
    lat_min_vp = LAT1 - 3
    lat_max_vp = LAT0 + 3

    vis_lons, vis_lats = [], []

    def scan(ring):
        for c in ring:
            lon = c[0] if c[0] >= 0 else c[0] + 360
            lat = c[1]
            if lon_min_vp <= lon <= lon_max_vp and lat_min_vp <= lat <= lat_max_vp:
                vis_lons.append(lon)
                vis_lats.append(lat)

    gtype  = geometry["type"]
    coords = geometry["coordinates"]
    if gtype == "Polygon":
        for ring in coords:
            scan(ring)
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                scan(ring)

    if not vis_lons:
        return None, None

    cx = sum(vis_lons) / len(vis_lons)
    cy = sum(vis_lats) / len(vis_lats)
    # Прижимаем к viewport с отступом
    cx = max(LON0 + 1.5, min(LON1 - 1.5, cx))
    cy = max(LAT1 + 1.5, min(LAT0 - 1.5, cy))
    return cx, cy


def load_world_geojson():
    return load_geojson_from(WORLD_GEOJSON_URLS, "стран мира")


def build_neighbor_paths(world_data):
    """Строит SVG-пути для соседних стран (со штриховкой).
    Возвращает (paths, label_data) где label_data = [(name_ru, lon, lat), ...]."""
    if not world_data:
        return [], []
    paths      = []
    label_data = []
    skipped    = 0
    features   = world_data.get("features", [])
    for feature in features:
        props = feature.get("properties", {})
        geom  = feature.get("geometry")
        if not geom:
            continue

        fid  = str(feature.get("id", ""))
        name = (props.get("name") or props.get("NAME") or
                props.get("ADMIN") or props.get("sovereignt") or "")
        iso3 = (props.get("ISO_A3") or props.get("iso_a3") or fid or "")

        # Пропускаем Россию
        if iso3 == "RUS" or fid == "RUS":
            continue
        if "Russia" in str(name) or "Россия" in str(name):
            continue

        if not is_in_viewport(geom):
            skipped += 1
            continue

        path_d = geometry_to_path_eps(geom, epsilon=3.0)
        if not path_d:
            continue

        safe = str(name).replace('"', "'").replace("&", "&amp;")
        paths.append(
            f'  <path class="neighbor" data-name="{safe}" '
            f'fill="url(#neighborHatch)" stroke="#a09880" stroke-width="5" '
            f'd="{path_d}"/>'
        )

        # Подпись: ищем русское название
        name_ru = COUNTRY_NAMES_RU.get(str(name), "")
        if not name_ru:
            # Попробуем другие поля
            for alt in ("ADMIN", "sovereignt", "NAME"):
                alt_val = props.get(alt, "")
                if alt_val and alt_val in COUNTRY_NAMES_RU:
                    name_ru = COUNTRY_NAMES_RU[alt_val]
                    break
        if name_ru:
            cx, cy = compute_visible_center(geom)
            if cx is not None:
                label_data.append((name_ru, cx, cy))

        print(f"  + {name}" + (f" → {name_ru}" if name_ru else ""))
    print(f"  (за пределами viewport: {skipped})")
    return paths, label_data


def build_neighbor_labels_svg(label_data):
    """Генерирует подписи только для крупных соседних стран — строго по ручным координатам."""
    # Только страны которые хорошо видны на карте + точные координаты
    FIXED_LABELS = [
        ("Норвегия",      16.0, 68.0),
        ("Финляндия",     26.0, 63.5),
        ("Швеция",        17.0, 62.0),
        ("Эстония",       25.5, 58.7),
        ("Латвия",        25.0, 57.0),
        ("Литва",         24.0, 55.8),
        ("Беларусь",      28.5, 53.5),
        ("Украина",       32.0, 49.5),
        ("Польша",        20.0, 52.0),
        ("Румыния",       25.0, 45.8),
        ("Казахстан",     67.0, 49.0),
        ("Монголия",     103.0, 46.5),
        ("Китай",        103.0, 40.0),
        ("Грузия",        43.5, 42.2),
        ("Азербайджан",   47.5, 40.5),
        ("Туркменистан",  58.5, 40.5),
        ("Узбекистан",    63.0, 41.5),
        ("Северная Корея",127.5, 40.5),
        ("США",          195.0, 64.5),
    ]
    lines = []
    for name_ru, lon, lat in FIXED_LABELS:
        if not (LON0 <= lon <= LON1 and LAT1 <= lat <= LAT0):
            continue
        x, y = geo_to_svg(lon, lat)
        xi, yi = int(round(x)), int(round(y))
        safe = name_ru.replace("&", "&amp;").replace("<", "&lt;")
        lines.append(
            f'  <text x="{xi}" y="{yi}"'
            f' font-family="Segoe UI, Arial, sans-serif"'
            f' font-size="115" font-style="italic" font-weight="400"'
            f' fill="#5a5040" text-anchor="middle" dominant-baseline="middle"'
            f' opacity="0.65" letter-spacing="6" pointer-events="none"'
            f'>{safe}</text>'
        )
    return "\n".join(lines)


def build_grid_svg():
    """Сетка отключена."""
    return ""


def build_sea_labels_svg():
    """Генерирует <text>-элементы для названий морей.
    Поддерживает (lon, lat, text, fsize) и (lon, lat, text, fsize, angle).
    """
    lines = []
    for item in SEA_LABEL_DEFS:
        lon, lat, text, fsize = item[:4]
        angle = item[4] if len(item) > 4 else 0

        if not (LON0 <= lon <= LON1 and LAT1 <= lat <= LAT0):
            continue
        x, y = geo_to_svg(lon, lat)
        x_i, y_i = int(round(x)), int(round(y))
        safe = text.replace("&", "&amp;").replace("<", "&lt;")

        # Атласный стиль: разреженные заглавные буквы, курсив, чуть прозрачные
        rotate = f' transform="rotate({angle},{x_i},{y_i})"' if angle != 0 else ""
        lines.append(
            f'  <text x="{x_i}" y="{y_i}"'
            f' font-family="Segoe UI, Arial, sans-serif"'
            f' font-size="{fsize}" font-style="italic" font-weight="400"'
            f' fill="#1e4a6a" text-anchor="middle" dominant-baseline="middle"'
            f' opacity="0.80" letter-spacing="14" pointer-events="none"'
            f'{rotate}>{safe}</text>'
        )
    return "\n".join(lines)


def build_defs_svg():
    """Генерирует секцию <defs> с паттерном штриховки."""
    return f'''\
  <defs>
    <!-- Диагональная штриховка для соседних стран -->
    <pattern id="neighborHatch" patternUnits="userSpaceOnUse" width="400" height="400">
      <rect width="400" height="400" fill="{NEIGHBOR_FILL}"/>
      <line x1="-400" y1="400" x2="0"   y2="0"   stroke="{NEIGHBOR_LINE}" stroke-width="16"/>
      <line x1="0"    y1="400" x2="400" y2="0"   stroke="{NEIGHBOR_LINE}" stroke-width="16"/>
      <line x1="400"  y1="400" x2="800" y2="0"   stroke="{NEIGHBOR_LINE}" stroke-width="16"/>
    </pattern>
  </defs>'''


# ── Получить ISO-код по свойствам feature ─────────────────────────────────
def get_iso(props):
    # Сначала ищем готовый ISO-код в свойствах
    for key in ("iso_3166_2", "ISO_3166_2", "iso3166_2", "code", "region_code"):
        val = props.get(key, "")
        if val and val.startswith("RU-"):
            return val

    # Ищем по названию
    for key in ("name", "Name", "NAME", "name_ru", "region", "shapeName"):
        name = props.get(key, "")
        if not name:
            continue
        # Пробуем русские названия
        if name in NAME_TO_ISO:
            return NAME_TO_ISO[name]
        # Пробуем английские
        if name in NAME_TO_ISO_EN:
            return NAME_TO_ISO_EN[name]
        # Частичное совпадение (нечувствительное к регистру)
        name_lower = name.lower()
        for known_name, iso in NAME_TO_ISO.items():
            if known_name.lower() in name_lower or name_lower in known_name.lower():
                return iso
        for known_name, iso in NAME_TO_ISO_EN.items():
            if known_name.lower() in name_lower or name_lower in known_name.lower():
                return iso

    return None


# ── Загрузить GeoJSON (универсальная) ─────────────────────────────────────
def load_geojson_from(urls, label="регионов"):
    for url in urls:
        print(f"  Пробую: {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode("utf-8"))
            n = len(data.get("features", []))
            print(f"  OK: загружено {n} {label}")
            return data
        except Exception as e:
            print(f"  ОШИБКА: {e}")
    return None

def load_geojson():
    return load_geojson_from(GEOJSON_URLS, "регионов РФ")

def load_ukraine_geojson():
    return load_geojson_from(UKRAINE_GEOJSON_URLS, "областей Украины")


# ── Получить ISO-код из украинского feature ───────────────────────────────
def get_ua_iso(props):
    # Проверяем все возможные ключи с названиями (GADM использует NAME_1)
    for key in ("NAME_1", "name", "Name", "NAME", "name_ua", "shapeName", "region", "NAME_0"):
        val = props.get(key, "")
        if not val:
            continue
        if val in UA_NAME_TO_RU_ISO:
            return UA_NAME_TO_RU_ISO[val]
        val_lower = val.lower()
        for ua_name, iso in UA_NAME_TO_RU_ISO.items():
            if ua_name.lower() in val_lower or val_lower in ua_name.lower():
                return iso
    return None


# ── Цвет по индексу (7-цветная схема, соседние регионы разных цветов) ──────
def pick_color(idx):
    return PALETTE[idx % len(PALETTE)]


# ── Русские имена регионов (для data-name) ─────────────────────────────────
ISO_TO_RUNAME = {v: k for k, v in NAME_TO_ISO.items()
                 if not k.endswith("АО") and "автономный" not in k.lower()
                 or k not in NAME_TO_ISO}

# Явные имена для отображения
ISO_TO_DISPLAY = {
    "RU-AD":  "Республика Адыгея",
    "RU-AL":  "Республика Алтай",
    "RU-ALT": "Алтайский край",
    "RU-AMU": "Амурская область",
    "RU-ARK": "Архангельская область",
    "RU-AST": "Астраханская область",
    "RU-BA":  "Республика Башкортостан",
    "RU-BEL": "Белгородская область",
    "RU-BRY": "Брянская область",
    "RU-BU":  "Республика Бурятия",
    "RU-CE":  "Чеченская Республика",
    "RU-CHE": "Челябинская область",
    "RU-CHU": "Чукотский автономный округ",
    "RU-CR":  "Республика Крым",
    "RU-CU":  "Чувашская Республика",
    "RU-DA":  "Республика Дагестан",
    "RU-DN":  "Донецкая Народная Республика",
    "RU-IN":  "Республика Ингушетия",
    "RU-IRK": "Иркутская область",
    "RU-IVA": "Ивановская область",
    "RU-KAM": "Камчатский край",
    "RU-KB":  "Кабардино-Балкарская Республика",
    "RU-KC":  "Карачаево-Черкесская Республика",
    "RU-KDA": "Краснодарский край",
    "RU-KEM": "Кемеровская область",
    "RU-KGD": "Калининградская область",
    "RU-KGN": "Курганская область",
    "RU-KHA": "Хабаровский край",
    "RU-KHM": "Ханты-Мансийский автономный округ",
    "RU-KIR": "Кировская область",
    "RU-KK":  "Республика Хакасия",
    "RU-KL":  "Республика Калмыкия",
    "RU-KLU": "Калужская область",
    "RU-KO":  "Республика Коми",
    "RU-KOS": "Костромская область",
    "RU-KR":  "Республика Карелия",
    "RU-KRS": "Курская область",
    "RU-KS":  "Херсонская область",
    "RU-KYA": "Красноярский край",
    "RU-LEN": "Ленинградская область",
    "RU-LIP": "Липецкая область",
    "RU-LU":  "Луганская Народная Республика",
    "RU-MAG": "Магаданская область",
    "RU-ME":  "Республика Марий Эл",
    "RU-MO":  "Республика Мордовия",
    "RU-MOS": "Московская область",
    "RU-MOW": "Москва",
    "RU-MUR": "Мурманская область",
    "RU-NEN": "Ненецкий автономный округ",
    "RU-NGR": "Новгородская область",
    "RU-NIZ": "Нижегородская область",
    "RU-NVS": "Новосибирская область",
    "RU-OMS": "Омская область",
    "RU-ORL": "Орловская область",
    "RU-ORE": "Оренбургская область",
    "RU-PER": "Пермский край",
    "RU-PNZ": "Пензенская область",
    "RU-PRI": "Приморский край",
    "RU-PSK": "Псковская область",
    "RU-ROS": "Ростовская область",
    "RU-RYA": "Рязанская область",
    "RU-SA":  "Республика Саха (Якутия)",
    "RU-SAK": "Сахалинская область",
    "RU-SAM": "Самарская область",
    "RU-SAR": "Саратовская область",
    "RU-SE":  "Республика Северная Осетия — Алания",
    "RU-SEV": "Севастополь",
    "RU-SMO": "Смоленская область",
    "RU-SPE": "Санкт-Петербург",
    "RU-STA": "Ставропольский край",
    "RU-SVE": "Свердловская область",
    "RU-TA":  "Республика Татарстан",
    "RU-TAM": "Тамбовская область",
    "RU-TOM": "Томская область",
    "RU-TUL": "Тульская область",
    "RU-TVE": "Тверская область",
    "RU-TY":  "Республика Тыва",
    "RU-TYU": "Тюменская область",
    "RU-UD":  "Удмуртская Республика",
    "RU-ULY": "Ульяновская область",
    "RU-VGG": "Волгоградская область",
    "RU-VLA": "Владимирская область",
    "RU-VLG": "Вологодская область",
    "RU-VOR": "Воронежская область",
    "RU-YAN": "Ямало-Ненецкий автономный округ",
    "RU-YAR": "Ярославская область",
    "RU-YEV": "Еврейская автономная область",
    "RU-ZAB": "Забайкальский край",
    "RU-ZP":  "Запорожская область",
}


# ── Основная функция ───────────────────────────────────────────────────────
def main():
    replace = "--replace" in sys.argv
    out_path = os.path.join(os.path.dirname(__file__), "russia_new.svg")

    print("=" * 46)
    print("  build_svg.py -- generator karty Rossii")
    print("=" * 46)
    print()

    print("1. Загружаем GeoJSON...")
    geojson = load_geojson()
    if geojson is None:
        print("\n[ОШИБКА] Не удалось загрузить GeoJSON ни с одного источника.")
        print("   Проверьте интернет-соединение.")
        sys.exit(1)

    features = geojson.get("features", [])
    print(f"\n2. Обрабатываем {len(features)} регионов...")

    paths_svg = []
    found_isos = set()
    skipped = []

    for i, feature in enumerate(features):
        props    = feature.get("properties", {})
        geometry = feature.get("geometry")
        if not geometry:
            continue

        iso = get_iso(props)
        if iso is None:
            name = (props.get("name") or props.get("Name") or props.get("NAME") or
                    props.get("region") or "?")
            skipped.append(name)
            continue

        if iso in found_isos:
            # Уже есть — дописываем к существующему (объединяем пути)
            continue

        found_isos.add(iso)
        display_name = ISO_TO_DISPLAY.get(iso, props.get("name", iso))
        path_d = geometry_to_path(geometry)
        if not path_d:
            continue

        color = pick_color(i)
        paths_svg.append(
            f'  <path id="{iso}" data-name="{display_name}" '
            f'style="fill:{color};stroke:#202020;stroke-width:8;" '
            f'd="{path_d}"/>'
        )
        print(f"  + {iso:10s} {display_name}")

    if skipped:
        print(f"\n  [!] Не распознано {len(skipped)} из РФ-GeoJSON:")
        for s in skipped[:20]:
            print(f"    - {s}")

    # ── Шаг 2.5: добавляем 6 регионов из украинского GeoJSON ─────────────
    still_missing = MISSING_FROM_RUSSIA - found_isos
    if still_missing:
        print(f"\n2.5. Загружаем недостающие регионы из GeoJSON Украины...")
        print(f"     Ищем: {', '.join(sorted(still_missing))}")
        ua_geojson = load_ukraine_geojson()
        if ua_geojson:
            ua_features = ua_geojson.get("features", [])
            for feature in ua_features:
                props    = feature.get("properties", {})
                geometry = feature.get("geometry")
                if not geometry:
                    continue
                iso = get_ua_iso(props)
                if iso is None or iso not in still_missing or iso in found_isos:
                    continue
                found_isos.add(iso)
                still_missing.discard(iso)
                display_name = ISO_TO_DISPLAY.get(iso, iso)
                path_d = geometry_to_path(geometry)
                if not path_d:
                    print(f"  [!] Пустой путь для {iso}")
                    continue
                color = pick_color(len(paths_svg))
                paths_svg.append(
                    f'  <path id="{iso}" data-name="{display_name}" '
                    f'style="fill:{color};stroke:#202020;stroke-width:8;" '
                    f'd="{path_d}"/>'
                )
                print(f"  + {iso:10s} {display_name}")
        if still_missing:
            print(f"\n  [!] В GeoJSON не найдены: {', '.join(sorted(still_missing))}")
    else:
        print("\n  Все 89 регионов найдены в основном GeoJSON.")

    # ── Шаг 2.6: fallback — встроенные координаты ─────────────────────────
    still_missing2 = MISSING_FROM_RUSSIA - found_isos
    if still_missing2:
        print(f"\n2.6. Использую встроенные координаты для {len(still_missing2)} регионов...")
        for iso in sorted(still_missing2):
            if iso not in FALLBACK_COORDS:
                print(f"  [!] Нет координат для {iso}")
                continue
            coords = FALLBACK_COORDS[iso]
            display_name = ISO_TO_DISPLAY.get(iso, iso)
            # Строим geometry-like dict
            geometry = {
                "type": "Polygon",
                "coordinates": [[[c[0], c[1]] for c in coords]],
            }
            path_d = geometry_to_path(geometry)
            if not path_d:
                print(f"  [!] Пустой путь для {iso}")
                continue
            color = pick_color(len(paths_svg))
            paths_svg.append(
                f'  <path id="{iso}" data-name="{display_name}" '
                f'style="fill:{color};stroke:#202020;stroke-width:8;" '
                f'd="{path_d}"/>'
            )
            found_isos.add(iso)
            print(f"  + {iso:10s} {display_name} (встроенные координаты)")

    missing = set(ISO_TO_DISPLAY.keys()) - found_isos
    if missing:
        print(f"\n  [!] Итого отсутствуют ({len(missing)}):")
        for m in sorted(missing):
            print(f"    - {m}: {ISO_TO_DISPLAY[m]}")

    # ── Шаг 3: загружаем страны мира ─────────────────────────────────────────
    print("\n3. Загружаем страны мира для фона карты...")
    world_data = load_world_geojson()
    if world_data:
        neighbor_paths, label_data = build_neighbor_paths(world_data)
    else:
        neighbor_paths, label_data = [], []
    print(f"   Добавлено соседних стран: {len(neighbor_paths)}, подписей: {len(label_data)}")

    # ── Шаг 4: собираем все вспомогательные слои ─────────────────────────────
    defs_section            = build_defs_svg()
    grid_section            = build_grid_svg()
    neighbor_labels_section = build_neighbor_labels_svg(label_data)
    sea_labels_section      = build_sea_labels_svg()

    # ── Шаг 5: записываем SVG ─────────────────────────────────────────────────
    print(f"\n4. Записываем SVG ({len(paths_svg)} регионов, "
          f"{len(neighbor_paths)} соседних стран)...")

    nl = chr(10)
    svg_content = f'''<?xml version="1.0" encoding="utf-8"?>
<svg width="100%" height="100%"
     viewBox="0 0 {VIEWBOX_W} {VIEWBOX_H}"
     xmlns="http://www.w3.org/2000/svg">
  <title>Карта России</title>
  <!-- Регионов РФ: {len(paths_svg)} | Соседей: {len(neighbor_paths)} | Проекция: экваториальная -->

{defs_section}

  <!-- Фон — цвет моря -->
  <rect x="0" y="0" width="{VIEWBOX_W}" height="{VIEWBOX_H}" fill="{SEA_COLOR}"/>

  <!-- Соседние страны (диагональная штриховка) -->
  <g id="neighbors">
{nl.join(neighbor_paths)}
  </g>

  <!-- Подписи соседних стран -->
  <g id="neighborLabels" pointer-events="none">
{neighbor_labels_section}
  </g>

  <!-- Регионы России -->
  <g id="russia">
{nl.join(paths_svg)}
  </g>

  <!-- Подписи морей и океанов -->
  <g id="seaLabels" pointer-events="none">
{sea_labels_section}
  </g>

</svg>'''

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    size_kb = os.path.getsize(out_path) // 1024
    print(f"  [ok] Zapisano: {out_path} ({size_kb} KB)")

    if replace:
        import shutil
        backup = out_path.replace("russia_new.svg", "russia_old.svg")
        orig   = out_path.replace("russia_new.svg", "russia.svg")
        if os.path.exists(orig):
            shutil.copy2(orig, backup)
            print(f"  [ok] Backup: {backup}")
        shutil.copy2(out_path, orig)
        os.remove(out_path)
        print(f"  [ok] Zameneno: {orig}")

    print()
    print("=" * 46)
    print(f"  Gotovo! Regionov: {len(paths_svg)} iz ~89")
    print("=" * 46)
    print()
    if not replace:
        print("Sleduyuschiy shag:")
        print("  python build_svg.py --replace")
        print("  (zamenit russia.svg avtomaticheski)")
        print("  ili vruchnuyu: pereimenuyte russia_new.svg -> russia.svg")


if __name__ == "__main__":
    main()
