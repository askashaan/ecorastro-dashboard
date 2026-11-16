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

# Estilos CSS con alto contraste y diseño 1:1 con Bolt (Restaurado)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    
    .stApp { background-color: #0d1f15 !important; color: #f7f4ed !important; }
    #MainMenu, footer, header { visibility: hidden; }

    .bolt-nav { display: flex; align-items: center; justify-content: space-between; padding: 12px 24px; background-color: #0d1f15; border-bottom: 1px solid rgba(247, 244, 237, 0.1); margin-bottom: 32px; }
    .bolt-logo { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.2rem; color: #f7f4ed; }
    .bolt-btn-nav { background-color: #e76f51; color: #ffffff !important; padding: 8px 20px; border-radius: 9999px; font-weight: 600; font-size: 0.875rem; text-decoration: none; }
    
    .hero-title { font-size: 3rem; font-weight: 700; color: #f7f4ed; line-height: 1.1; margin-bottom: 16px; }
    .hero-subtitle { color: rgba(247, 244, 237, 0.8); font-size: 1.125rem; max-width: 650px; line-height: 1.6; margin-bottom: 24px; }
    .badge-pill { display: inline-flex; align-items: center; gap: 6px; background-color: rgba(247, 244, 237, 0.1); border: 1px solid rgba(247, 244, 237, 0.2); padding: 4px 14px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; color: #f7f4ed; margin-bottom: 16px; }
    
    div[data-testid="stRadio"] label { color: #f7f4ed !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. Header & Navegación (Bolt UI)
# ---------------------------------------------------------
st.markdown("""
<div class="bolt-nav">
    <div class="bolt-logo">🌱 EcoRastro</div>
    <div><a href="#dashboard" class="bolt-btn-nav">Ver Dashboard</a></div>
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
<div style="background-color: #f7
