import streamlit as st
import folium
from folium import plugins
from streamlit_folium import st_folium
import ee
import json

# ---------------------------------------------------------
# 1. Configuración de Página & Estilos TailWind / Bolt Theme
# ---------------------------------------------------------
st.set_page_config(
    page_title="EcoRastro | Inteligencia Geoespacial B2G",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inyección de estilos con la paleta exacta de Bolt (forest-900, cream, terracotta)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .stApp {
        background-color: #0d1f15; /* forest-900 */
        color: #f7f4ed; /* cream */
    }

    /* Ocultar elementos sobrantes de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Paleta de Colores Bolt */
    .bg-forest-900 { background-color: #0d1f15; }
    .bg-forest-800 { background-color: #142e20; }
    .bg-cream { background-color: #f7f4ed; }
    .text-cream { color: #f7f4ed; }
    .text-terracotta-300 { color: #f39a77; }
    .text-terracotta-400 { color: #e76f51; }
    .text-forest-800 { color: #142e20; }
    .text-forest-600 { color: #2d5a3f; }
    .text-forest-500 { color: #407b57; }

    /* Estilos de Tarjetas */
    .hero-card {
        background: linear-gradient(135deg, rgba(20, 46, 32, 0.95) 0%, rgba(13, 31, 21, 0.8) 100%);
        border: 1px solid rgba(247, 244, 237, 0.15);
        border-radius: 24px;
        padding: 40px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.3);
    }

    .problem-card {
        background-color: #f7f4ed;
        color: #142e20;
        border-radius: 24px;
        padding: 32px;
    }

    .source-item {
        background-color: rgba(20, 46, 32, 0.05);
        border: 1px dashed rgba(20, 46, 32, 0.2);
        border-radius: 16px;
        padding: 12px 16px;
        margin-bottom: 12px;
    }

    .badge-saas {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background-color: rgba(247, 244, 237, 0.1);
        border: 1px solid rgba(247, 244, 237, 0.2);
        padding: 6px 16px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        color: #f7f4ed;
    }

    /* Radio buttons estilizados como toggle */
    div[data-testid="stRadio"] > label {
        color: #f7f4ed !important;
        font-weight: 600;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] {
        background-color: #142e20;
        padding: 8px;
        border-radius: 16px;
        border: 1px solid rgba(247, 244, 237, 0.15);
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. Inicialización Segura de Google Earth Engine
# ---------------------------------------------------------
@st.cache_resource
def init_earth_engine():
    try:
        if "GCP_SERVICE_ACCOUNT" in st.secrets:
            secret_val = st.secrets["GCP_SERVICE_ACCOUNT"]
            service_account_info = json.loads(secret_val) if isinstance(secret_val, str) else dict(secret_val)
            
            client_email = service_account_info.get("client_email")
            private_key = service_account_info.get("private_key")
            project_id = service_account_info.get("project_id")
            
            credentials = ee.ServiceAccountCredentials(client_email, key_data=private_key)
            ee.Initialize(credentials, project=project_id)
            return True
        else:
            ee.Initialize()
            return True
    except Exception:
        return False

ee_status = init_earth_engine()

# Coordenadas ampliavas del Parque O'Higgins
coordenadas_parque = [
    [-70.6678, -33.4530], [-70.6525, -33.4530],
    [-70.6525, -33.4715], [-70.6678, -33.4715], [-70.6678, -33.4530]
]

# Función Satelital GEE
def obtener_capa_satelital(capa_tipo):
    if not ee_status: return None, 0.0
    try:
        parque_geometry = ee.Geometry.Polygon(coordenadas_parque)
        coleccion = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(parque_geometry).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 15)).sort("system:time_start", False)
        imagen = coleccion.first()

        if "Normal" in capa_tipo:
            corte = imagen.select(["B4", "B3", "B2"]).clip(parque_geometry)
            vis_params = {"min": 0, "max": 2500, "gamma": 1.2}
            return corte.getMapId(vis_params)["tile_fetcher"].url_format, 0.0
        elif "NDVI" in capa_tipo:
            corte = imagen.normalizedDifference(["B8", "B4"]).rename("NDVI").clip(parque_geometry)
            vis_params = {"min": 0.1, "max": 0.7, "palette": ["#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#91cf60", "#1a9850"]}
        elif "NDMI" in capa_tipo:
            ndvi = imagen.normalizedDifference(["B8", "B4"])
            ndmi = imagen.normalizedDifference(["B8A", "B11"])
            corte = ndmi.updateMask(ndvi.gt(0.15)).rename("NDMI").clip(parque_geometry)
            vis_params = {"min": -0.05, "max": 0.3, "palette": ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#abd9e9", "#74add1", "#4575b4"]}
        elif "NDBI" in capa_tipo:
            corte = imagen.normalizedDifference(["B11", "B8"]).rename("NDBI").clip(parque_geometry)
            vis_params = {"min": -0.2, "max": 0.2, "palette": ["#1a9850", "#91cf60", "#d9ef8b", "#fee08b", "#fc8d59", "#d73027"]}

        map_id = corte.getMapId(vis_params)
        mean_stat = corte.reduceRegion(reducer=ee.Reducer.mean(), geometry=parque_geometry, scale=10).getInfo()
        promedio_val = list(mean_stat.values())[0] if mean_stat and list(mean_stat.values())[0] is not None else 0.0
        return map_id["tile_fetcher"].url_format, promedio_val
    except Exception:
        return None, 0.0

# ---------------------------------------------------------
# 3. COMPONENTE 1: HERO SECTION (Réplica Hero.tsx)
# ---------------------------------------------------------
st.markdown("""
<div class="hero-card">
    <div class="badge-saas">
        <span style="height: 8px; width: 8px; background-color: #f39a77; border-radius: 50%; display: inline-block;"></span>
        Plataforma SaaS B2G
    </div>
    <h1 style="font-size: 2.8rem; font-weight: 700; margin-top: 16px; line-height: 1.1;">
        Inteligencia Geoespacial para el Monitoreo de <span class="text-terracotta-300">Áreas Verdes</span>
    </h1>
    <p style="font-size: 1.1rem; color: rgba(247, 244, 237, 0.85); margin-top: 16px; max-width: 700px; line-height: 1.6;">
        EcoRastro procesa datos satelitales (Sentinel-2) para unificar la información biológica urbana. 
        Entregamos un panel de control en tiempo real sobre la salud vegetal y el estrés hídrico, transformando datos fragmentados en decisiones operativas.
    </p>
    <div style="display: flex; gap: 40px; margin-top: 36px; padding-top: 24px; border-top: 1px solid rgba(247, 244, 237, 0.15);">
        <div>
            <div style="font-size: 11px; text-transform: uppercase; color: rgba(247, 244, 237, 0.6); font-weight: 600;">⏰ Actualización</div>
            <div style="font-size: 1.2rem; font-weight: 700; margin-top: 4px;">Cada 5 días</div>
        </div>
        <div>
            <div style="font-size: 11px; text-transform: uppercase; color: rgba(247, 244, 237, 0.6); font-weight: 600;">🛰️ Fuente</div>
            <div style="font-size: 1.2rem; font-weight: 700; margin-top: 4px;">Sentinel-2</div>
        </div>
        <div>
            <div style="font-size: 11px; text-transform: uppercase; color: rgba(247, 244, 237, 0.6); font-weight: 600;">💧 Índices</div>
            <div style="font-size: 1.2rem; font-weight: 700; margin-top: 4px;">NDVI · NDMI · NDBI</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.write("")
st.write("")

# ---------------------------------------------------------
# 4. COMPONENTE 2: PROBLEM SECTION (Réplica ProblemSection.tsx)
# ---------------------------------------------------------
st.markdown("""
<div class="problem-card">
    <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; tracking-wider; color: #e76f51;">El Problema</div>
    <h2 class="text-forest-800" style="font-size: 2rem; font-weight: 700; margin-top: 8px;">
        La información biológica está fragmentada y desactualizada.
    </h2>
    <p class="text-forest-600" style="font-size: 1rem; margin-top: 12px; line-height: 1.6;">
        Actualmente no existe un monitoreo integral y periódico unificado en el Parque O'Higgins. 
        La información está dispersa entre inventarios municipales estáticos, datos de ciencia ciudadana y estudios académicos aislados. 
        Hace falta un sistema centralizado que mantenga los datos actualizados para la gestión real.
    </p>
    
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 24px;">
        <div class="source-item">
            <strong class="text-forest-800" style="display: block; font-size: 14px;">🏢 Inventarios municipales</strong>
            <span class="text-forest-500" style="font-size: 12px;">Estáticos y sin actualización</span>
        </div>
        <div class="source-item">
            <strong class="text-forest-800" style="display: block; font-size: 14px;">👥 Ciencia ciudadana</strong>
            <span class="text-forest-500" style="font-size: 12px;">Registros puntuales y dispersos</span>
        </div>
        <div class="source-item">
            <strong class="text-forest-800" style="display: block; font-size: 14px;">🎓 Estudios académicos</strong>
            <span class="text-forest-500" style="font-size: 12px;">Aislados y de corto alcance</span>
        </div>
    </div>
    
    <div style="background-color: #fdf0ed; border: 1px solid #f8c9bc; border-radius: 16px; padding: 16px; margin-top: 20px; display: flex; align-items: center; gap: 16px;">
        <div style="background-color: #e76f51; color: white; border-radius: 12px; padding: 10px; font-weight: bold;">⚡ Impacto</div>
        <div class="text-forest-800" style="font-weight: 600; font-size: 15px;">
            De un ecosistema fragmentado a 1 sola plataforma centralizada con actualización cada 5 días.
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.write("")
st.write("")

# ---------------------------------------------------------
# 5. COMPONENTE 3: SATELLITE DASHBOARD (Réplica SatelliteDashboard.tsx + GEE Real)
# ---------------------------------------------------------
st.markdown("""
<div style="margin-bottom: 16px;">
    <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: #f39a77; display: flex; align-items: center; gap: 6px;">
        🛰️ Dashboard satelital en vivo
    </div>
    <h2 style="font-size: 2.2rem; font-weight: 700; color: #f7f4ed; margin-top: 6px;">
        Parque O'Higgins: salud vegetal y estrés hídrico
    </h2>
    <p style="color: rgba(247, 244, 237, 0.7); font-size: 0.95rem;">
        Cambia entre capas para leer el estado de la vegetación o la disponibilidad de agua del parque.
    </p>
</div>
""", unsafe_allow_html=True)

# Toggle de Capas en la interfaz
capa_seleccionada = st.radio(
    "Seleccionar Capa Satelital:",
    ["🌳 NDVI (Salud Vegetal)", "💧 NDMI (Estrés Hídrico)", "🏢 NDBI (Islas de Calor / Cemento)", "📸 Normal (RGB)"],
    horizontal=True
)

# Mapa Interactivo de Folium
m = folium.Map(location=[-33.4625, -70.6588], zoom_start=15, tiles="OpenStreetMap")

plugins.LocateControl(
    position="bottomright", drawCircle=False, keepCurrentZoomLevel=True,
    strings={"title": "Mostrar mi ubicación actual", "popup": "Estás aquí"}
).add_to(m)

tile_url, promedio_val = obtener_capa_satelital(capa_seleccionada)

if tile_url:
    folium.TileLayer(tiles=tile_url, attr="Copernicus Sentinel-2", name=capa_seleccionada, overlay=True, control=True).add_to(m)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Fuente Satelital", "ESA Sentinel-2")
    if "Normal" not in capa_seleccionada:
        siglas = capa_seleccionada.split()[1]
        col2.metric(f"Promedio Zona ({siglas})", f"{promedio_val:.3f}")
        col3.metric("Evaluación General", "Estrés Detectado" if promedio_val < 0.1 else "Óptimo")
    else:
        col2.metric("Modo de Vista", "Color Verdadero")
        col3.metric("Frecuencia", "5 días")
else:
    folium.Polygon(locations=[[lat, lng] for lng, lat in coordenadas_parque], color="#10b981", fill=True, fill_opacity=0.3).add_to(m)

# Mapa interactivo reactivo
map_data = st_folium(m, width="100%", height=560, key=capa_seleccionada)

# Intervención Táctica en Terreno (Google Maps GPS)
if map_data and map_data.get("last_clicked"):
    lat, lng = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
    st.success(f"📍 **Punto de Intervención Seleccionado:** Coordenadas `{lat:.5f}, {lng:.5f}`")
    gmaps_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}&travelmode=walking"
    st.markdown(f'<a href="{gmaps_url}" target="_blank" style="display:inline-block; padding:12px 24px; background-color:#e76f51; color:white; font-weight:700; border-radius:12px; text-decoration:none;">🚶‍♂️ Iniciar Navegación Táctica (Google Maps)</a>', unsafe_allow_html=True)

# Leyenda Desplegable
with st.expander("📖 Guía de Interpretación de Capas"):
    st.markdown("""
    * **🌳 NDVI:** Vigor foliar. Rojo = suelo desnudo o seco; Verde = vegetación frondosa.
    * **💧 NDMI:** Humedad interna vegetal (*enmascarada en cemento*). Rojo = déficit de riego urgente; Azul = excelente reserva de agua.
    * **🏢 NDBI:** Densidad construida. Focos rojos indican zonas con mayor acumulación de calor urbano.
    """)

st.caption("EcoRastro B2G | Sistema de Apoyo a la Toma de Decisiones para la Red de Corredores Vivos (GORE Santiago).")
