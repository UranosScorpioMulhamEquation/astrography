import datetime
import os
from typing import Dict, List, Tuple, Any, Optional

import geonamescache
import pandas as pd
import pytz
import streamlit as st
import swisseph as swe
from timezonefinder import TimezoneFinder

# ==========================================
# 0. تهيئة مسار ملفات الـ Ephemeris والإعدادات
# ==========================================
EPHE_PATH = "./ephe"
if not os.path.exists(EPHE_PATH):
    os.makedirs(EPHE_PATH)

swe.set_ephe_path(EPHE_PATH)

st.set_page_config(
    page_title="النظام المتقدم للأستروكارتوغرافيا",
    page_icon="✨",
    layout="wide"
)

# قاموس ترجمة وحصر الدول المعتمدة حصرياً (الشرق الأوسط وشمال أفريقيا، أمريكا، كندا، أستراليا، بريطانيا وأوروبا)
ARABIC_COUNTRIES = {
    # الشرق الأوسط وشمال أفريقيا (MENA)
    "United Arab Emirates": "الإمارات العربية المتحدة",
    "Saudi Arabia": "المملكة العربية السعودية",
    "Syria": "سوريا",
    "Egypt": "مصر",
    "Lebanon": "لبنان",
    "Jordan": "الأردن",
    "Iraq": "العراق",
    "Kuwait": "الكويت",
    "Qatar": "قطر",
    "Bahrain": "البحرين",
    "Oman": "سلطنة عمان",
    "Yemen": "اليمن",
    "Palestine": "فلسطين",
    "Sudan": "السودان",
    "Libya": "ليبيا",
    "Tunisia": "تونس",
    "Algeria": "الجزائر",
    "Morocco": "المغرب",
    
    # أمريكا الشمالية وكندا
    "United States": "الولايات المتحدة الأمريكية",
    "Canada": "كندا",
    
    # أستراليا
    "Australia": "أستراليا",
    
    # بريطانيا وأوروبا
    "United Kingdom": "المملكة المتحدة (بريطانيا)",
    "France": "فرنسا",
    "Germany": "ألمانيا",
    "Italy": "إيطاليا",
    "Spain": "إسبانيا",
    "Greece": "اليونان",
    "Switzerland": "سويسرا",
    "Sweden": "السويد",
    "Netherlands": "هولندا",
    "Belgium": "بلجيكا",
    "Austria": "النمسا",
    "Portugal": "البرتغال",
    "Poland": "بولندا",
    "Norway": "النرويج",
    "Denmark": "الدنمارك",
    "Finland": "فنلندا",
    "Ireland": "أيرلندا",
    "Czech Republic": "جمهورية التشيك",
    "Hungary": "المجر",
    "Romania": "رومانيا",
    "Croatia": "كرواتيا",
    "Slovakia": "سلوفاكيا",
    "Slovenia": "سلوفينيا",
    "Bulgaria": "بلغاريا",
    "Serbia": "صربيا",
    "Estonia": "إستونيا",
    "Latvia": "لاتفيا",
    "Lithuania": "ليتوانيا"
}

ALLOWED_COUNTRY_CODES = {
    'AE', 'SA', 'SY', 'EG', 'LB', 'JO', 'IQ', 'KW', 'QA', 'BH', 'OM', 'YE', 'PS', 'SD', 'LY', 'TN', 'DZ', 'MA',
    'US', 'CA', 'AU',
    'GB', 'FR', 'DE', 'IT', 'ES', 'GR', 'CH', 'SE', 'NL', 'BE', 'AT', 'PT', 'PL', 'NO', 'DK', 'FI', 'IE', 'CZ', 'HU', 'RO', 'HR', 'SK', 'SI', 'BG', 'RS', 'EE', 'LV', 'LT'
}

def get_arabic_country_name(eng_name: str) -> str:
    return ARABIC_COUNTRIES.get(eng_name, eng_name)

# ==========================================
# 1. خدمات البيانات الجغرافية والزمنية
# ==========================================
@st.cache_data
def load_geo_data() -> Tuple[geonamescache.GeonamesCache, Dict[str, str], List[str], Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    gc = geonamescache.GeonamesCache()
    countries = gc.get_countries()
    cities = gc.get_cities()

    # حصر الخريطة والدول المتاحة فقط بالدول المسموحة ومترجمة للعربية
    country_map = {get_arabic_country_name(c["name"]): code for code, c in countries.items() if code in ALLOWED_COUNTRY_CODES}
    sorted_arabic_countries = sorted(list(country_map.keys()))

    cities_by_country: Dict[str, List[Dict[str, Any]]] = {}
    filtered_cities = []
    
    for c_code, c_data in countries.items():
        if c_code not in ALLOWED_COUNTRY_CODES:
            continue
        eng_country_name = c_data["name"]
        arabic_c_name = get_arabic_country_name(eng_country_name)
        c_cities = [city for city in cities.values() if city["countrycode"] == c_code]
        c_cities_sorted = sorted(c_cities, key=lambda x: x["population"], reverse=True)
        
        cities_by_country[c_code] = c_cities_sorted
        
        for city in c_cities_sorted:
            if city.get("population", 0) > 80000:
                lat = city.get("latitude", 0)
                if -65.0 <= lat <= 65.0:
                    city_copy = city.copy()
                    city_copy["arabic_country"] = arabic_c_name
                    filtered_cities.append(city_copy)

    return gc, country_map, sorted_arabic_countries, cities_by_country, filtered_cities

gc, country_map, country_list, cities_by_country, filtered_cities = load_geo_data()

@st.cache_resource
def get_tz_finder() -> TimezoneFinder:
    return TimezoneFinder()

tf = get_tz_finder()

def get_utc_julian_day(date_obj: datetime.date, time_obj: datetime.time, tz_str: str) -> float:
    local_tz = pytz.timezone(tz_str)
    dt = datetime.datetime.combine(date_obj, time_obj)
    local_dt = local_tz.localize(dt)
    utc_dt = local_dt.astimezone(pytz.utc)
    return swe.julday(
        utc_dt.year,
        utc_dt.month,
        utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0,
    )

# ==========================================
# 2. القواميس الفلكية للكواكب السبعة الأساسية
# ==========================================
PLANET_DICTIONARY = {
    "الشمس (Sun)": {
        "nature": "إيجابي/داعم",
        "MC": "خط وسط السماء: ذروة الشهرة، الصعود المهني والقيادة الظاهرة والنجاح العام.",
        "AC": "خط الطالع: تعزيز الثقة الشخصية، الحيوية الجسدية وهيبة الحضور.",
        "DC": "خط الغارب: شراكات مع شخصيات نافذة ومرموقة وعلاقات علنية بارزة.",
        "IC": "خط جذر السماء: استقرار داخلي وتصالح مع الهوية والعائلة والجذور."
    },
    "القمر (Moon)": {
        "nature": "إيجابي/عاطفي",
        "MC": "خط وسط السماء: نجاح في مهن الجمهور، الإعلام، التغذية والرأي العام.",
        "AC": "خط الطالع: حساسية عالية، جاذبية شعبية وتفاعل وجداني مع المحيط.",
        "DC": "خط الغارب: علاقات عميقة تعتمد على الألفة العاطفية والحدس المشترك.",
        "IC": "خط جذر السماء: أفضل خط على الإطلاق للاستقرار العاطفي، السكن، وشراء العقارات والأمان النفسي."
    },
    "عطارد (Mercury)": {
        "nature": "إيجابي/فكري",
        "MC": "خط وسط السماء: نجاح في التجارة، الأعمال الحرة، الإعلام، والكتابة والتدريس.",
        "AC": "خط الطالع: نشاط ذهني متوقد، سرعة في البديهة والتواصل الفعّال.",
        "DC": "خط الغارب: نقاشات مثمرة، عقود تجارية ناجحة وشراكات فكرية.",
        "IC": "خط جذر السماء: بيئة منزلية محفزة للبحث، الدراسة والتواصل."
    },
    "الزهرة (Venus)": {
        "nature": "إيجابي للغاية",
        "MC": "خط وسط السماء: ازدهار مالي، مشاريع فنية أو تجارية مربحة وذوق رفيع.",
        "AC": "خط الطالع: سحر شخصي أخاذ، جاذبية عالية وحب وتقدير من المحيط.",
        "DC": "خط الغارب: أقوى وأفضل خط للحب، الزواج السعيد والشراكات العاطفية والانسجام.",
        "IC": "خط جذر السماء: منزل جميل مريح، بحبوحة عيش وراحة نفسية عميقة."
    },
    "المريخ (Mars)": {
        "nature": "طاقي/متحارب",
        "MC": "خط وسط السماء: طموح جريء، إنجاز مهني سريع، تنافسية عالية وقيادة ميدانية.",
        "AC": "خط الطالع: طاقة جسدية عالية وحماس، قد يصاحبها اندفاع أو صدامات.",
        "DC": "خط الغارب: توتر محتمل أو احتكاك في الشراكات، ومواجهات تنافسية.",
        "IC": "خط جذر السماء: أجواء متوترة في البيت وعدم استقرار أو إصلاحات منزلية مستمرة."
    },
    "المشتري (Jupiter)": {
        "nature": "إيجابي/حظ ووفرة",
        "MC": "خط وسط السماء: قمة النجاح الوظيفي، الحظ الوافر، الترقيات والسمعة الطيبة الواسعة.",
        "AC": "خط الطالع: تفاؤل، انفتاح، صحة ممتازة وفرص توسع شخصي واسعة.",
        "DC": "خط الغارب: شراكات مباركة، عقود دولية ناجحة وزواج سعيد ومثمر.",
        "IC": "خط جذر السماء: منزل واسع، استقرار مادي ومعنوي عميق وبركة في السكن."
    },
    "زحل (Saturn)": {
        "nature": "ضاغطة/اختبارات",
        "MC": "خط وسط السماء: مسؤوليات ثقيلة، ضغوط مهنية وجهود مضنية تؤتي ثمارها ببطء شديد.",
        "AC": "خط الطالع: جدية مفرطة، شعور بالثقل، اختبارات في التحمل والصبر الشخصي.",
        "DC": "خط الغارب: شراكات جادة، جافة، أو تأخر وتحديات في الارتباط والزواج.",
        "IC": "خط جذر السماء: أعباء عائلية ثقيلة، شعور بالوحدة أو جفاء عاطفي في بيئة السكن."
    }
}

# ==========================================
# 3. واجهة المستخدم (Streamlit UI)
# ==========================================
st.title("🌟 النظام المتقدم للأستروكارتوغرافيا الاحترافي")
st.markdown("### المسح الفلكي الجغرافي للدول (برمجة الفلكي الدكتور استرو رادار)")
st.markdown("---")

with st.sidebar:
    st.header(" بيانات المولود")
    name = st.text_input("اسم المستفيد", "ميار")
    
    current_year = datetime.date.today().year
    birth_date = st.date_input(
        "تاريخ الميلاد", 
        value=datetime.date(1981, 4, 17),
        min_value=datetime.date(1900, 1, 1),
        max_value=datetime.date(current_year, 12, 31)
    )
    birth_time = st.time_input("ساعة الميلاد (التوقيت المحلي)", datetime.time(11, 30), step=datetime.timedelta(minutes=1))
    
    st.header(" مكان الولادة الجغرافي")
    birth_country_name = st.selectbox("دولة الميلاد", country_list, index=country_list.index("سوريا") if "سوريا" in country_list else 0)
    birth_c_code = country_map.get(birth_country_name, 'SY')
    
    birth_cities = cities_by_country.get(birth_c_code, [])
    birth_city_names = [c["name"] for c in birth_cities] if birth_cities else ["Default"]
    birth_city_name = st.selectbox("مدينة الميلاد", birth_city_names)
    
    b_city_data = next((c for c in birth_cities if c["name"] == birth_city_name), {"latitude": 33.5138, "longitude": 36.2765})
    b_lat, b_lon = b_city_data["latitude"], b_city_data["longitude"]
    
    tz_str = tf.timezone_at(lng=b_lon, lat=b_lat) or "UTC"
    
    st.markdown("---")
    st.header(" نطاق ونوع البحث")
    search_mode = st.radio("خيارات البحث الجغرافي", ["مسح كامل لجميع الدول المتاحة (تصنيف أفضل وأسوأ 10 دول)", "البحث في دولة محددة فقط"])
    
    selected_target_country = None
    if search_mode == "البحث في دولة محددة فقط":
        selected_target_country = st.selectbox("اختر الدولة المستهدفة للتحليل", country_list)

    st.markdown("---")
    st.info("ℹ️ **الدول المعتمدة:** الشرق الأوسط، شمال أفريقيا، أمريكا، كندا، أستراليا، بريطانيا وأوروبا.\n\n**الأوربت الفلكي:** ثابت عند 1.0 درجة.")

    analyze_btn = st.button("🚀 بدء التحليل الفلكي الجغرافي", type="primary")

# ==========================================
# 4. محرك الحسابات الفلكية وتحليل أداء الدول
# ==========================================
if analyze_btn:
    FIXED_ORB = 1.0  # المعيار العالمي الثابت للأوربت
    
    with st.spinner("جاري إجراء الحسابات الفلكية وتحليل الأثر الكوكبي على الدول والمدن..."):
        jd = get_utc_julian_day(birth_date, birth_time, tz_str)
        
        planets_to_calc = {
            "الشمس (Sun)": swe.SUN,
            "القمر (Moon)": swe.MOON,
            "عطارد (Mercury)": swe.MERCURY,
            "الزهرة (Venus)": swe.VENUS,
            "المريخ (Mars)": swe.MARS,
            "المشتري (Jupiter)": swe.JUPITER,
            "زحل (Saturn)": swe.SATURN
        }
        
        planet_longitudes = {}
        for p_name, p_id in planets_to_calc.items():
            res = swe.calc_ut(jd, p_id)
            planet_longitudes[p_name] = res[0][0]
        
        def angular_distance(l1, l2):
            diff = abs(l1 - l2)
            return diff if diff <= 180.0 else 360.0 - diff

        benefic_planets = ["الشمس (Sun)", "الزهرة (Venus)", "المشتري (Jupiter)", "القمر (Moon)", "عطارد (Mercury)"]
        malefic_planets = ["المريخ (Mars)", "زحل (Saturn)"]

        # تصفية المدن بناءً على خيار الدولة المحددة أو المسح الشامل
        cities_to_scan = filtered_cities
        if selected_target_country:
            cities_to_scan = [c for c in filtered_cities if c["arabic_country"] == selected_target_country]

        raw_hits = []

        for city in cities_to_scan:
            c_lat = city["latitude"]
            c_lon = city["longitude"]
            arabic_country = city["arabic_country"]
            
            try:
                houses = swe.houses_ex(jd, c_lat, c_lon, b'P')
                asc = houses[0][0]  
                ic = houses[0][3]   
                dc = houses[0][6]   
                mc = houses[0][9]   
            except Exception:
                continue
            
            for p_name, p_lon in planet_longitudes.items():
                dict_info = PLANET_DICTIONARY[p_name]
                
                distances = [
                    ("MC (وسط السماء)", angular_distance(p_lon, mc), dict_info['MC']),
                    ("AC (الطالع)", angular_distance(p_lon, asc), dict_info['AC']),
                    ("DC (الغارب)", angular_distance(p_lon, dc), dict_info['DC']),
                    ("IC (جذر السماء)", angular_distance(p_lon, ic), dict_info['IC'])
                ]
                
                for angle_name, dist, desc in distances:
                    if dist <= FIXED_ORB:
                        power_score = round(100 - (dist / FIXED_ORB) * 50, 2)
                        hit_type = "benefic" if p_name in benefic_planets else "malefic"
                        
                        raw_hits.append({
                            "city_name": city["name"],
                            "country_name": arabic_country,
                            "planet": p_name,
                            "angle": angle_name,
                            "orb": round(dist, 3),
                            "power": power_score,
                            "type": hit_type,
                            "desc": desc
                        })

        st.success(" تم إنجاز التحليل الفلكي الجغرافي بنجاح!")
        st.markdown(f"## 🌍 تقرير الأستروكارتوغرافيا لـ: {name}")
        st.markdown(f"**نطاق التأثير (Orb):** ثابت عند **$1.0^\\circ$** (التوصية العالمية الصارمة)")

        if selected_target_country:
            # العرض في حالة اختيار دولة محددة
            st.markdown(f"### 📍 نتائج التحليل الخاص بـ: **{selected_target_country}**")
            if not raw_hits:
                st.warning(f"⚠️ **منطقة محايدة فلكياً:** لا يمر أي خط كوكبي رئيسي ضمن النطاق المؤثر ($\\le 1.0^\\circ$) عبر مدن {selected_target_country}.")
            else:
                df_country = pd.DataFrame([{
                    "المدينة": h["city_name"],
                    "الكوكب": h["planet"],
                    "الوتد": h["angle"],
                    "البعد (Orb)": f"{h['orb']}°",
                    "نوع التأثير": "داعم/إيجابي" if h["type"] == "benefic" else "ضاغط/تحدي"
                } for h in sorted(raw_hits, key=lambda x: x["orb"])])
                st.dataframe(df_country, width='stretch')

                st.markdown("#### التفاصيل التحليلية للمدن المكتشفة:")
                for hit in sorted(raw_hits, key=lambda x: x["orb"]):
                    box_color = "#27ae60" if hit["type"] == "benefic" else "#c0392b"
                    st.markdown(f"""
                    <div style="border-left: 5px solid {box_color}; padding: 10px; margin: 8px 0; background: #fdfefe; border-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                        <h4 style="margin: 0; color: #2c3e50;">📍 مدينة: <b>{hit['city_name']}</b></h4>
                        <p style="margin: 4px 0;"><b>الكوكب:</b> {hit['planet']} | <b>الوتد:</b> <code>{hit['angle']}</code> | <b>البعد الدقيق (Orb):</b> {hit['orb']}°</p>
                        <p style="margin: 4px 0; color: #555;"><b>التأثير الفلكي:</b> {hit['desc']}</p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            # العرض في حالة المسح الكامل لتصنيف أفضل 10 دول وأسوأ 10 دول بالترتيب
            best_countries_dict = {}
            worst_countries_dict = {}

            for hit in raw_hits:
                c_name = hit["country_name"]
                if hit["type"] == "benefic":
                    if c_name not in best_countries_dict or hit["orb"] < best_countries_dict[c_name]["orb"]:
                        best_countries_dict[c_name] = hit
                else:
                    if c_name not in worst_countries_dict or hit["orb"] < worst_countries_dict[c_name]["orb"]:
                        worst_countries_dict[c_name] = hit

            # ترتيب أفضل 10 دول بالترتيب حسب الأورب والأكثر دقة
            sorted_best_countries = sorted(list(best_countries_dict.values()), key=lambda x: x["orb"])[:10]
            
            # ترتيب أسوأ 10 دول بالترتيب حسب الأورب والأكثر ضغطاً
            sorted_worst_countries = sorted(list(worst_countries_dict.values()), key=lambda x: x["orb"])[:10]

            st.markdown("### 🏆 أفضل 10 دول بالترتيب (تأثيرات الشمس، الزهرة، المشتري، القمر، عطارد):")
            if not sorted_best_countries:
                st.warning("⚠️ لم يتم رصد تقاطعات داعمة قوية ضمن الأوربت المحدد.")
            else:
                df_best_c = pd.DataFrame([{
                    "الترتيب": idx + 1,
                    "الدولة": h["country_name"],
                    "أبرز مدينة متأثرة": h["city_name"],
                    "الكوكب الداعم": h["planet"],
                    "الوتد": h["angle"],
                    "البعد (Orb)": f"{h['orb']}°"
                } for idx, h in enumerate(sorted_best_countries)])
                st.dataframe(df_best_c, width='stretch')

            st.markdown("### ⚠️ أسوأ 10 دول بالترتيب (تأثيرات المريخ وزحل الضاغطة):")
            if not sorted_worst_countries:
                st.info("ℹ️ لم يتم رصد دول واقعة تحت تأثيرات ضاغطة لزحل والمريخ ضمن الأوربت المحدد.")
            else:
                df_worst_c = pd.DataFrame([{
                    "الترتيب": idx + 1,
                    "الدولة": h["country_name"],
                    "أبرز مدينة متأثرة": h["city_name"],
                    "الكوكب الضاغط": h["planet"],
                    "الوتد": h["angle"],
                    "البعد (Orb)": f"{h['orb']}°"
                } for idx, h in enumerate(sorted_worst_countries)])
                st.dataframe(df_worst_c, width='stretch')

            # تجهيز التقرير الـ HTML
            html_content = f"""
            <!DOCTYPE html>
            <html lang="ar" dir="rtl">
            <head>
                <meta charset="UTF-8">
                <title>تقرير الأستروكارتوغرافيا المتقدم - {name}</title>
                <style>
                    body {{ font-family: 'Tahoma', sans-serif; margin: 40px; background: #f9f9f9; color: #333; }}
                    .header {{ text-align: center; border-bottom: 2px solid #2c3e50; padding-bottom: 20px; }}
                    h1 {{ color: #2c3e50; }}
                    .section {{ background: #fff; padding: 20px; margin-top: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    .card-best {{ border-left: 5px solid #27ae60; padding: 10px 15px; margin: 10px 0; background: #f1f9f5; }}
                    .card-worst {{ border-left: 5px solid #c0392b; padding: 10px 15px; margin: 10px 0; background: #fdf3f2; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>تقرير الأستروكارتوغرافيا لتصنيف الدول (أوربت {FIXED_ORB}°)</h1>
                    <p>المستفيد: <strong>{name}</strong> | تاريخ الميلاد: {birth_date} ({birth_time})</p>
                </div>
                
                <div class="section">
                    <h2>🏆 أفضل 10 دول بالترتيب</h2>
            """
            
            for idx, h in enumerate(sorted_best_countries):
                html_content += f"""
                <div class="card-best">
                    <h3>المركز {idx+1}: {h['country_name']} (مدينة {h['city_name']})</h3>
                    <p><b>الكوكب:</b> {h['planet']} | <b>الوتد:</b> {h['angle']} | <b>Orb:</b> {h['orb']}°</p>
                    <p><b>التأثير:</b> {h['desc']}</p>
                </div>
                """
                
            html_content += """
                </div>
                <div class="section">
                    <h2>⚠️ أسوأ 10 دول بالترتيب</h2>
            """
            
            for idx, h in enumerate(sorted_worst_countries):
                html_content += f"""
                <div class="card-worst">
                    <h3 style="color: #c0392b;">المركز {idx+1}: {h['country_name']} (مدينة {h['city_name']})</h3>
                    <p><b>الكوكب الضاغط:</b> {h['planet']} | <b>الوتد:</b> {h['angle']} | <b>Orb:</b> {h['orb']}°</p>
                    <p><b>التأثير:</b> {h['desc']}</p>
                </div>
                """
                
            html_content += """
                </div>
                <div style="text-align: center; margin-top: 30px; color: #7f8c8d; font-size: 12px;">
                    تم إعداد هذا التقرير عبر محرك الأستروكارتوغرافيا المتقدم - جميع الحقوق محفوظة للفلكي استرو رادار.
                </div>
            </body>
            </html>
            """

            st.markdown("---")
            st.download_button(
                label="📥 تحميل تقرير ترتيب الدول الكامل (HTML)",
                data=html_content,
                file_name=f"AstroCartography_Top_Countries_Report_{name.replace(' ', '_')}.html",
                mime="text/html"
            )