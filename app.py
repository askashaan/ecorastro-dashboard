import streamlit as st
import folium
from streamlit_folium import st_folium
import ee

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
Monitoreo satelital para la identificación de islas de calor y planificación de infraestructura verde urbana.
""")

# ---------------------------------------------------------
# 2. Inicialización Segura de Google Earth Engine
# ---------------------------------------------------------
@st.cache_resource
def init_earth_engine():
    try:
        # Reemplaza 'tu-proyecto-gee-id' por tu ID real de proyecto en Google Cloud cuando lo tengas.
        ee.Initialize(project='tu-proyecto-gee-id')
        return True
    except Exception as e:
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

# ---------------------------------------------------------
# 3. Función de Obtención de Capas
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

        if "NDVI" in capa_tipo:
            corte = imagen.normalizedDifference(["B8", "B4"]).rename("NDVI").clip(parque_geometry)
            vis_params = {
                "min": 0.0, "max": 0.8,
                "palette": ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#d9ef8b", "#a6d96a", "#1a9850"]
            }
        else:
            corte = imagen.normalizedDifference(["B3", "B8"]).rename("NDWI").clip(parque_geometry)
            vis_params = {
                "min": -0.5, "max": 0.2,
                "palette": ["#d73027", "#f46d43", "#fee08b", "#e0f3f8", "#91bfdb", "#4575b4"]
            }

        map_id = corte.getMapId(vis_params)
        mean_stat = corte.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=parque_geometry,
            scale=10
        ).getInfo()

        val = list(mean_stat.values())[0] if mean_stat else 0.0
        return map_id["tile_fetcher"].url_format, val

    except Exception:
        return None, 0.0

# ---------------------------------------------------------
# 4. Interfaz & Renderizado
# ---------------------------------------------------------
st.sidebar.header("⚙️ Filtros Satelitales")
capa_seleccionada = st.sidebar.radio(
    "Selecciona el indicador multiespectral:",
    ["NDVI (Salud Vegetal)", "NDWI (Estrés Hídrico)"]
)

# Mapa Base
m = folium.Map(
    location=[-33.4625, -70.6588],
    zoom_start=15,
    tiles="CartoDB dark_matter"
)

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
    # Mensaje informativo elegante sin romper la app
    st.sidebar.warning("⚠️ Modo Demostración Activo: API de Google Earth Engine pendiente de credenciales en la nube.")
    
    # Dibujar el polígono real del Parque O'Higgins como referencia espacial
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
