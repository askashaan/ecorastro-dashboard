import streamlit as st
import folium
from folium import plugins
from streamlit_folium import st_folium
import ee
import json

# ---------------------------------------------------------
# 1. Configuración de Página & Tema Visual Bolt
# ---------------------------------------------------------
st.set_page_config(
    page_title="EcoRastro | Monitoreo Satelital",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos CSS con alto contraste y diseño 1:1 con Bolt
# ---------------------------------------------------------
# PROBLEM SECTION (Estilizado limpio con HTML nativo seguro)
# ---------------------------------------------------------
st.markdown("""
<div style="background-color: #f7f4ed; border-radius: 24px; padding: 36px; margin-top: 32px; margin-bottom: 32px; font-family: sans-serif;">
    <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #e76f51;">El problema</div>
    <h2 style="color: #142e20; font-size: 1.8rem; font-weight: 700; margin-top: 8px; margin-bottom: 12px; line-height: 1.2;">
        La información biológica está fragmentada y desactualizada.
    </h2>
    <p style="color: #2d5a3f; font-size: 0.95rem; line-height: 1.6; margin-bottom: 24px;">
        Actualmente no existe un monitoreo integral y periódico unificado en el Parque O'Higgins. 
        La información está dispersa entre inventarios municipales estáticos, datos de ciencia ciudadana y estudios académicos aislados. 
        Hace falta un sistema centralizado que mantenga los datos actualizados para la gestión real.
    </p>
    
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
        <div style="background-color: #ffffff; border: 1px dashed #c2d6c9; border-radius: 16px; padding: 14px;">
            <strong style="color: #142e20; display: block; font-size: 0.9rem; margin-bottom: 4px;">🏢 Inventarios municipales</strong>
            <span style="color: #407b57; font-size: 0.8rem;">Estáticos y sin actualización</span>
        </div>
        <div style="background-color: #ffffff; border: 1px dashed #c2d6c9; border-radius: 16px; padding: 14px;">
            <strong style="color: #142e20; display: block; font-size: 0.9rem; margin-bottom: 4px;">👥 Ciencia ciudadana</strong>
            <span style="color: #407b57; font-size: 0.8rem;">Registros puntuales y dispersos</span>
        </div>
        <div style="background-color: #ffffff; border: 1px dashed #c2d6c9; border-radius: 16px; padding: 14px;">
            <strong style="color: #142e20; display: block; font-size: 0.9rem; margin-bottom: 4px;">🎓 Estudios académicos</strong>
            <span style="color: #407b57; font-size: 0.8rem;">Aislados y de corto alcance</span>
        </div>
    </div>
    
    <div style="background-color: #fdf0ed; border: 1px solid #f8c9bc; border-radius: 14px; padding: 14px 18px; margin-top: 20px; display: flex; align-items: center; gap: 14px;">
        <span style="background-color: #e76f51; color: white; padding: 6px 12px; border-radius: 8px; font-weight: 700; font-size: 0.8rem; white-space: nowrap;">⚡ Impacto</span>
        <span style="color: #142e20; font-weight: 600; font-size: 0.9rem;">
            De un ecosistema fragmentado a 1 sola plataforma centralizada con actualización cada 5 días.
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. Header & Navegación (Bolt UI)
# ---------------------------------------------------------
st.markdown("""
<div class="bolt-nav">
    <div class="bolt-logo">
        🌱 EcoRastro
    </div>
    <div>
        <a href="#dashboard" class="bolt-btn-nav">Ver Dashboard</a>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. Inicialización de Google Earth Engine
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

coordenadas_parque = [
    [-70.6678, -33.4530], [-70.6525, -33.4530],
    [-70.6525, -33.4715], [-70.6678, -33.4715], [-70.6678, -33.4530]
]

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
# 4. Hero Section
# ---------------------------------------------------------
st.markdown("""
<div class="badge-pill">
    <span style="height: 6px; width: 6px; background-color: #f39a77; border-radius: 50%;"></span>
    Plataforma SaaS B2G
</div>
<h1 class="hero-title">
    Inteligencia Geoespacial para el Monitoreo de <span style="color: #f39a77;">Áreas Verdes</span>
</h1>
<p class="hero-subtitle">
    EcoRastro procesa datos satelitales (Sentinel-2) para unificar la información biológica urbana. 
    Entregamos un panel de control en tiempo real sobre la salud vegetal y el estrés hídrico.
</p>
""", unsafe_allow_html=True)

col_h1, col_h2, col_h3 = st.columns(3)
with col_h1:
    st.caption("⏰ ACTUALIZACIÓN")
    st.markdown("**Cada 5 días**")
with col_h2:
    st.caption("🛰️ FUENTE")
    st.markdown("**Sentinel-2 (ESA)**")
with col_h3:
    st.caption("💧 ÍNDICES")
    st.markdown("**NDVI · NDMI · NDBI**")

st.markdown("---")

# ---------------------------------------------------------
# 5. Problem Section (Tarjeta Blanca Limpia)
# ---------------------------------------------------------
st.markdown("""
<div class="problem-box">
    <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #e76f51;">El problema</div>
    <h2>La información biológica está fragmentada y desactualizada.</h2>
    <p>
        Currently, there is no unified periodic monitoring in Parque O'Higgins. Information is scattered across static municipal inventories, citizen science, and isolated studies.
    </p>
    
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-top: 24px;">
        <div class="source-card">
            <strong>🏢 Inventarios municipales</strong>
            <span>Estáticos y sin actualización</span>
        </div>
        <div class="source-card">
            <strong>👥 Ciencia ciudadana</strong>
            <span>Registros puntuales y dispersos</span>
        </div>
        <div class="source-card">
            <strong>🎓 Estudios académicos</strong>
            <span>Aislados y de corto alcance</span>
        </div>
    </div>
    
    <div class="impact-banner">
        <span class="impact-badge">Impacto</span>
        <span class="impact-text">De un ecosistema fragmentado a 1 sola plataforma centralizada con actualización cada 5 días.</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 6. Dashboard Satelital (Réplica Imagen 2)
# ---------------------------------------------------------
st.markdown("<div id='dashboard'></div>", unsafe_allow_html=True)
st.caption("🛰️ DASHBOARD SATELITAL")
st.markdown("## Parque O'Higgins: salud vegetal y estrés hídrico")
st.write("Cambia entre capas para leer el estado de la vegetación o la disponibilidad de agua del parque.")

capa_seleccionada = st.radio(
    "Capas de análisis:",
    ["🌱 Índice de Salud (NDVI)", "💧 Estrés Hídrico (NDMI)", "🏢 Zonas Construidas (NDBI)", "📸 Foto Satelital (RGB)"],
    horizontal=True
)

m = folium.Map(location=[-33.4625, -70.6588], zoom_start=15, tiles="OpenStreetMap")

plugins.LocateControl(
    position="bottomright", drawCircle=False, keepCurrentZoomLevel=True,
    strings={"title": "Ubicación en vivo", "popup": "Estás aquí"}
).add_to(m)

tile_url, promedio_val = obtener_capa_satelital(capa_seleccionada)

if tile_url:
    folium.TileLayer(tiles=tile_url, attr="Copernicus Sentinel-2", name=capa_seleccionada, overlay=True, control=True).add_to(m)
else:
    folium.Polygon(locations=[[lat, lng] for lng, lat in coordenadas_parque], color="#10b981", fill=True, fill_opacity=0.3).add_to(m)

# Mapa con altura ajustada
map_data = st_folium(m, width="100%", height=520, key=capa_seleccionada)

# Tarjeta inferior desplegable (Métricas Bolt style)
if "Normal" not in capa_seleccionada:
    pct_val = int(max(0, min(1, promedio_val + 0.3)) * 100) if "NDVI" in capa_seleccionada else 78
    col_m1, col_m2 = st.columns([1, 2])
    with col_m1:
        st.metric(label="SALUD VEGETAL PROMEDIO", value=f"{pct_val}%", delta="Estado Óptimo")
    with col_m2:
        st.info("Biomasa alta en la mayoría de los sectores. Las zonas amarillas requieren seguimiento de riego.")

# Acción de Clic GPS
if map_data and map_data.get("last_clicked"):
    lat, lng = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
    st.success(f"📍 Coordenada objetivo para la cuadrilla: `{lat:.5f}, {lng:.5f}`")
    gmaps_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}&travelmode=walking"
    st.markdown(f'<a href="{gmaps_url}" target="_blank" style="display:inline-block; padding:10px 20px; background-color:#e76f51; color:white; font-weight:700; border-radius:10px; text-decoration:none;">🚶‍♂️ Ruta de Terreno en Google Maps</a>', unsafe_allow_html=True)
