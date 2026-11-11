import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import json

# ---------------------------------------------------------
# 1. Configuración de Página
# ---------------------------------------------------------
st.set_page_config(
    page_title="EcoRastro | Planificación de Corredores Verdes",
    page_icon="🛰️",
    layout="wide"
)

st.title("🛰️ EcoRastro: Inteligencia Geoespacial & Corredores Verdes")
st.markdown("""
Plataforma B2G de apoyo a la toma de decisiones para la **Municipalidad de Santiago y el GORE**. 
Monitoreo satelital (*Sentinel-2 vía Google Earth Engine*) para la identificación de islas de calor y planificación de infraestructura verde urbana.
""")

# ---------------------------------------------------------
# 2. Inicialización Segura de Google Earth Engine
# ---------------------------------------------------------
@st.cache_resource
def init_earth_engine():
    try:
        if "GCP_SERVICE_ACCOUNT" in st.secrets:
            secret_val = st.secrets["GCP_SERVICE_ACCOUNT"]
            if isinstance(secret_val, str):
                service_account_info = json.loads(secret_val)
            else:
                service_account_info = dict(secret_val)
            
            client_email = service_account_info.get("client_email")
            private_key = service_account_info.get("private_key")
            project_id = service_account_info.get("project_id")
            
            credentials = ee.ServiceAccountCredentials(client_email, key_data=private_key)
            ee.Initialize(credentials, project=project_id)
            return True
        else:
            ee.Initialize()
            return True
    except Exception as e:
        st.sidebar.error(f"⚠️ Error GEE: {str(e)}")
        return False

ee_status = init_earth_engine()

# Coordenadas reales del Parque O'Higgins
coordenadas_parque = [
    [-70.6625, -33.4578],
    [-70.6552, -33.4578],
    [-70.6552, -33.4672],
    [-70.6625, -33.4672],
    [-70.6625, -33.4578]
]

# Coordenadas ampliadas para cubrir el Parque O'Higgins y bordes viales
coordenadas_parque = [
    [-70.6678, -33.4530],
    [-70.6525, -33.4530],
    [-70.6525, -33.4715],
    [-70.6678, -33.4715],
    [-70.6678, -33.4530]
]

# ---------------------------------------------------------
# 3. Función de Obtención de Capas Satelitales (Mejorada)
# ---------------------------------------------------------
def obtener_capa_satelital(capa_tipo):
    if not ee_status:
        return None, 0.0

    try:
        parque_geometry = ee.Geometry.Polygon(coordenadas_parque)
        coleccion = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(parque_geometry)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 15))
            .sort("system:time_start", False)
        )
        imagen = coleccion.first()
        promedio_val = 0.0

        if "Normal (RGB)" in capa_tipo:
            # Color verdadero (Bandas Roja, Verde, Azul)
            corte = imagen.select(["B4", "B3", "B2"]).clip(parque_geometry)
            vis_params = {"min": 0, "max": 2500, "gamma": 1.2}
            return corte.getMapId(vis_params)["tile_fetcher"].url_format, 0.0

        elif "NDVI" in capa_tipo:
            # Salud Vegetal (Rojo y NIR)
            corte = imagen.normalizedDifference(["B8", "B4"]).rename("NDVI").clip(parque_geometry)
            vis_params = {"min": 0.0, "max": 0.8, "palette": ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#d9ef8b", "#a6d96a", "#1a9850"]}
        
        elif "NDMI" in capa_tipo:
            # Estrés Hídrico en vegetación (NIR y SWIR)
            corte = imagen.normalizedDifference(["B8A", "B11"]).rename("NDMI").clip(parque_geometry)
            vis_params = {"min": -0.2, "max": 0.4, "palette": ["#d73027", "#fc8d59", "#fee08b", "#e0f3f8", "#91bfdb", "#4575b4"]}
            
        elif "NDBI" in capa_tipo:
            # Zonas Construidas / Asfalto (SWIR y NIR)
            corte = imagen.normalizedDifference(["B11", "B8"]).rename("NDBI").clip(parque_geometry)
            vis_params = {"min": -0.2, "max": 0.3, "palette": ["#1a9850", "#91cf60", "#d9ef8b", "#fee08b", "#fc8d59", "#d73027"]}

        map_id = corte.getMapId(vis_params)
        mean_stat = corte.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=parque_geometry,
            scale=10
        ).getInfo()

        if mean_stat:
            promedio_val = list(mean_stat.values())[0]
            
        return map_id["tile_fetcher"].url_format, promedio_val

    except Exception as e:
        st.sidebar.error(f"⚠️ Error procesando capa: {str(e)}")
        return None, 0.0

# ---------------------------------------------------------
# 4. Interfaz de Usuario & Mapa
# ---------------------------------------------------------
st.sidebar.header("⚙️ Filtros Satelitales")
capa_seleccionada = st.sidebar.radio(
    "Selecciona la capa de análisis:",
    [
        "📸 Mapa Normal (RGB)", 
        "🌳 NDVI (Salud Vegetal)", 
        "💧 NDMI (Estrés Hídrico/Humedad)", 
        "🏢 NDBI (Cemento y Asfalto)"
    ]
)

# Mapa Base OpenStreetMap (Limpio de errores de API key)
m = folium.Map(
    location=[-33.4625, -70.6588],
    zoom_start=15,
    tiles="OpenStreetMap"
)

tile_url, promedio_val = obtener_capa_satelital(capa_seleccionada)

tile_url, promedio_val = obtener_capa_satelital(capa_seleccionada)

if tile_url:
    folium.TileLayer(
        tiles=tile_url,
        attr="Google Earth Engine / Copernicus Sentinel-2",
        name=capa_seleccionada,
        overlay=True,
        control=True
    ).add_to(m)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Fuente de Datos", "Sentinel-2 (ESA)")
    col2.metric("Resolución Espacial", "10 metros / píxel")
    col3.metric(f"Promedio Real {capa_seleccionada.split()[0]}", f"{promedio_val:.3f}")
else:
    if not ee_status:
        st.sidebar.warning("⚠️ Modo Demostración Activo.")
    
    folium.Polygon(
        locations=[[lat, lng] for lng, lat in coordenadas_parque],
        color="#10b981" if "NDVI" in capa_seleccionada else "#38bdf8",
        fill=True,
        fill_opacity=0.3,
        popup="Polígono Objetivo: Parque O'Higgins"
    ).add_to(m)

st_folium(m, width="100%", height=550)

st.markdown("---")
st.caption("EcoRastro B2G | Sistema de Apoyo a la Toma de Decisiones para la Estrategia de Corredores Verdes (GORE / Municipalidad de Santiago).")

    
